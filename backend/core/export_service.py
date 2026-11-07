"""Bounded standard XLSX exports with current source authorization on every read.

This is an explicit public-data catalog, not an ORM/table dump. A changed source
or revoked grant invalidates the whole immutable download, never just its label.
"""
import hashlib,json,os,re,uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from tempfile import NamedTemporaryFile
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,IntegrityError
from django.db.models import Q,F
from django.http import Http404
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from .access import accessible_projects,role_for,company_id_for,is_super_admin
from .models import Project,Profile,Checklist,WorkAssignment,ClientOrganization,GovernanceAudit
from .export_models import DataExportJob,DataExportWorkerLease

SCHEMA_VERSION=1
MAX_ROWS=50000
PAGE_SIZE=200
MAX_PROJECTS=2000
TTL_HOURS=48
MAX_ACTIVE=2
MAX_DAILY=20
MAX_BYTES=30*1024*1024
MAX_TEXT_BYTES=64*1024*1024
HEADERS={
 'projects':('Project ID','Project','Company','Industry','Client','Workflow layers'),
 'tasks':('Record type','Task ID','Site ID','Project','Assignee','Status','Description','Updated at'),
 'sites':('Record type','Task ID','Site ID','Project','Assignee','Status','Description','Updated at'),
 'clients':('Client ID','Client','Company','Industry'),
 'people':('User ID','Username','Name','Email','Role','Active'),
 'checklists':('Checklist ID','Site ID','Project','Template revision','Section ID','Section','Field ID','Point','Required','Human answer','Updated at'),
 'photos':('Photo ID','Checklist ID','Site ID','Filename','Category','Capture time','Latitude','Longitude','Uploaded at'),
 'documents':('Document ID','Checklist ID','Site ID','Filename','File type','Bytes','Uploaded at'),
 'review_history':('Checklist ID','Site ID','Revision','Action','Level','Reviewer','Reason','Recorded at'),
 'dc_power':('Record ID','Checklist ID','Site ID','Row','Field','Reported value'),
 'tower_equipment':('Record ID','Checklist ID','Site ID','Row','Operator','Equipment type','Model','Reported dimension','Reported height','Reported azimuth','Empty ports','Sector or leg'),
 'electrical':('Record ID','Checklist ID','Site ID','Row','Reported voltage','Reported current R','Reported current Y','Reported current B','Remarks'),
 'outputs':('Output ID','Checklist ID','Site ID','Revision','Edition','Released','Sheet title','Drawing number','Created at'),
}
LABELS={'dc_power':'DC power inventory','tower_equipment':'Tower equipment inventory','electrical':'Electrical inventory','projects':'Projects','tasks':'Tasks','sites':'Sites','clients':'Clients','people':'People','checklists':'Checklist answers','photos':'Photo information','documents':'Document information','review_history':'Review history','outputs':'Drawing/output register'}
ADMIN={Profile.Roles.ADMIN,Profile.Roles.SUPER_ADMIN}
INTERNAL={Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.PROJECT_MANAGER}

def safe_cell(value):
 if value is None:return ''
 if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
 elif hasattr(value,'isoformat'):value=value.isoformat()
 text=ILLEGAL_CHARACTERS_RE.sub('',str(value))
 if len(text)>30000:raise ValidationError('A source cell exceeds the Excel safety limit; narrow or correct the source before exporting.')
 if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')):text="'"+text
 return text

def _actor(actor):
 actor=User.objects.get(pk=actor.pk)
 if not role_for(actor):raise PermissionDenied('An active unlocked account is required.')
 return actor

def catalog(actor):
 role=role_for(_actor(actor))
 allowed={'projects','tasks','sites','checklists','photos','outputs'}
 if role in ADMIN:allowed|={'clients','people'}
 if role in INTERNAL:allowed|={'documents','review_history'}
 if role==Profile.Roles.ENGINEER:allowed.add('documents')
 if role in INTERNAL or role==Profile.Roles.ENGINEER:allowed|={'dc_power','tower_equipment','electrical'}
 if role==Profile.Roles.SUPER_ADMIN:allowed={'projects','clients','people'}
 return {k:LABELS[k] for k in HEADERS if k in allowed}

def _principal(actor):return {'role':role_for(actor),'company_id':company_id_for(actor)}
def _audit(actor,job,action):
 GovernanceAudit.objects.create(actor=actor,actor_name=actor.username,action='data_export.'+action,details={'export_id':str(job.pk),'section':job.section,'company_id':job.company_id,'rows':job.row_count,'schema_version':job.schema_version})

def _projects(actor,parameters):
 qs=accessible_projects(actor)
 if parameters.get('project_id') is not None:qs=qs.filter(pk=parameters['project_id'])
 return qs

def request_export(actor,section,project_id=None,request_key=None):
 actor=_actor(actor)
 if section not in catalog(actor):raise PermissionDenied('This data section is unavailable for your role.')
 try:key=uuid.UUID(str(request_key));pid=int(project_id) if project_id not in (None,'') else None
 except (ValueError,TypeError,OverflowError):raise ValidationError('Choose a valid export request and project.') from None
 if pid is not None and (isinstance(project_id,bool) or pid<=0 or pid>9223372036854775807):raise ValidationError('Choose a valid project.')
 params={'project_id':pid}
 with transaction.atomic():
  # Actor row serializes quota checks and replay creation across workers.
  User.objects.select_for_update().get(pk=actor.pk)
  old=DataExportJob.objects.filter(owner=actor,request_key=key).first()
  if old:
   if old.section!=section or old.parameters.get('project_id')!=pid:raise ValidationError('This request was already used for a different export.')
   return old,False
  projects=_projects(actor,params)
  if pid and not projects.exists():raise PermissionDenied('Project is outside your current access.')
  ids=list(projects.order_by('pk').values_list('pk',flat=True)[:MAX_PROJECTS+1])
  if len(ids)>MAX_PROJECTS:raise ValidationError('Select one project; this request exceeds the project scope limit.')
  now=timezone.now()
  active=DataExportJob.objects.filter(owner=actor,status__in=['queued','running'],expires_at__gt=now).count()
  if active>=MAX_ACTIVE:raise ValidationError('Two exports are already queued or preparing. Wait for one to finish.')
  if DataExportJob.objects.filter(owner=actor,created_at__gte=now-timedelta(hours=24)).count()>=MAX_DAILY:raise ValidationError('The daily limit is 20 export requests. Try again after earlier requests age out.')
  params['project_ids']=ids
  job=DataExportJob.objects.create(owner=actor,company_id=company_id_for(actor),section=section,request_key=key,parameters=params,principal=_principal(actor),expires_at=now+timedelta(hours=TTL_HOURS))
  _audit(actor,job,'requested');return job,True

def _scopes(actor,job):
 actor=_actor(actor)
 if actor.pk!=job.owner_id or _principal(actor)!=job.principal:raise PermissionDenied('Account scope changed. Request a new export.')
 if job.section not in catalog(actor):raise PermissionDenied('Export role permission changed.')
 projects=_projects(actor,job.parameters).filter(pk__in=job.parameters['project_ids'])
 if set(projects.values_list('pk',flat=True))!=set(job.parameters['project_ids']):raise PermissionDenied('Project access changed. Request a new export.')
 return actor,projects

def _page(qs):
 last=0
 while True:
  page=list(qs.filter(pk__gt=last).order_by('pk')[:PAGE_SIZE])
  if not page:return
  for row in page:yield row
  last=page[-1].pk

def _surveys(actor,projects):
 from .task_explorer import scopes
 _,surveys,_=scopes(actor)
 return surveys.filter(project__in=projects).select_related('project','checklist_template')

def _verified_surveys(actor,projects):
 from .template_views import survey_access
 request=SimpleNamespace(user=actor)
 for c in _page(_surveys(actor,projects)):
  # Follow exact current detail-view rules, including current revision sharing.
  try:survey_access(request,c.pk)
  except (Http404,PermissionDenied):continue
  yield c

def rows(actor,job):
 actor,projects=_scopes(actor,job);section=job.section;role=role_for(actor)
 if section=='projects':
  for p in _page(projects.select_related('company','client_organization')):
   yield f'p:{p.pk}',[p.pk,p.name,str(p.company or ''),p.industry,str(p.client_organization or ''),p.review_layers]
 elif section=='clients':
  qs=ClientOrganization.objects.all() if is_super_admin(actor) else ClientOrganization.objects.filter(company_id=company_id_for(actor),industry_id=actor.profile.admin_industry_id)
  if job.parameters.get('project_id'):qs=qs.filter(projects__in=projects).distinct()
  for c in _page(qs.select_related('company','industry')):yield f'client:{c.pk}',[c.pk,c.name,str(c.company),str(c.industry)]
 elif section=='people':
  from .governance_views import workspace_members
  for u in _page(workspace_members(actor,projects,is_super_admin(actor)).select_related('profile')):
   yield f'user:{u.pk}',[u.pk,u.username,u.get_full_name(),u.email,u.profile.get_role_display(),u.is_active]
 elif section in {'tasks','sites'}:
  from .task_explorer import scopes
  _,checklists,assignments=scopes(actor)
  for c in _page(checklists.filter(project__in=projects).select_related('project','user')):
   yield f'c:{c.pk}:{c.updated_at.isoformat()}', ['Checklist',c.pk,c.site_id,c.project.name,c.user.username,c.get_status_display(),'',c.updated_at]
  for a in _page(assignments.filter(project__in=projects).select_related('project','assigned_to')):
   yield f'a:{a.pk}', ['Assignment',a.pk,a.site_id,a.project.name,a.assigned_to.username,a.get_status_display(),a.description,a.created_at]
 else:
  for c in _verified_surveys(actor,projects):
   version=f'c:{c.pk}:{c.updated_at.isoformat()}'
   if section=='checklists':
    from .category_intake import projected_checklist
    view=c if role==Profile.Roles.ENGINEER else projected_checklist(c)
    custom=(view.answer_data or {}).get('custom',{})
    for group in (c.schema_snapshot or {}).get('sections',[]):
     for field in group.get('fields',[]):
      yield version+':'+field['id'],[c.pk,c.site_id,c.project.name,c.checklist_template.version if c.checklist_template_id else '',group.get('id',''),group.get('title',''),field['id'],field.get('label',''),bool(field.get('required')),custom.get(field['id'],''),c.updated_at]
   elif section=='photos':
    from .category_intake import enabled as category_enabled,state as capture_state,review_state
    if role==Profile.Roles.CLIENT or category_enabled(c):
     if role==Profile.Roles.CLIENT:
      from .photo_views import client_photo_state
      photos=client_photo_state(c)['photos']
     elif role==Profile.Roles.ENGINEER:photos=capture_state(SimpleNamespace(user=actor),c.pk)['photos']
     else:photos=review_state(SimpleNamespace(user=actor),c.pk)['photos']
     for p in photos:
      m=p.get('metadata') or {};gps=m.get('gps') or {}
      yield version+':photo:'+str(p['id']),[p['id'],c.pk,c.site_id,p['filename'],p.get('group',''),m.get('captured_at',''),gps.get('latitude',''),gps.get('longitude',''),p.get('uploaded_at','')]
    else:
     for p in _page(c.photo_evidence.all()):
      m=p.metadata if isinstance(p.metadata,dict) else {};gps=m.get('gps') if isinstance(m.get('gps'),dict) else {}
      yield version+':photo:'+str(p.pk),[p.pk,c.pk,c.site_id,p.filename,p.group,m.get('captured_at',''),gps.get('latitude',''),gps.get('longitude',''),p.created_at]
   elif section=='documents':
    for d in _page(c.survey_documents.all()):yield version+':doc:'+str(d.pk),[d.pk,c.pk,c.site_id,d.filename,d.content_type,d.size,d.created_at]
   elif section=='review_history':
    from .revision_models import RevisionDecision
    for d in _page(RevisionDecision.objects.filter(revision__checklist=c).select_related('revision','actor')):
     yield version+':decision:'+str(d.pk),[c.pk,c.site_id,d.revision.number,d.action,d.level,d.actor.username,d.reason,d.created_at]
    for i,event in enumerate(c.review_history if isinstance(c.review_history,list) else []):
     if isinstance(event,dict):yield version+':legacy:'+str(i),[c.pk,c.site_id,'Legacy',event.get('action',event.get('decision','')),event.get('role',''),event.get('reviewer',event.get('by','')),event.get('reason',event.get('comment','')),event.get('at',event.get('date',''))]
   elif section in {'dc_power','tower_equipment','electrical'}:
    source,fields={'dc_power':(c.dc_power_data,('row_number','field_label','field_value')),'tower_equipment':(c.tower_equipment,('row_number','operator_type','equipment_type','model_name','dimension','height','azimuth','empty_port','sector_or_leg')),'electrical':(c.electrical_data,('row_number','voltage','current_r','current_y','current_b','remarks'))}[section]
    for item in _page(source.all()):yield version+':'+section+':'+str(item.pk),[item.pk,c.pk,c.site_id,*[getattr(item,name) for name in fields]]
   elif section=='outputs':
    from . import survey_processing as pipeline
    from .survey_processing_models import SurveyDrawingSet
    for output in _page(SurveyDrawingSet.objects.filter(revision__checklist=c).select_related('revision')):
     if role==Profile.Roles.CLIENT:
      if not output.released or not pipeline.current(output.revision):continue
      payload=pipeline.reviewed_payload(output.revision)
      if pipeline.release_gate(output.revision,payload) or output.review_digest!=pipeline.review_digest(payload):continue
     for i,sheet in enumerate(output.manifest.get('sheets',[])):
      yield version+':output:'+str(output.pk)+':'+str(i),[output.pk,c.pk,c.site_id,output.revision.number,output.edition,output.released,sheet.get('title',''),sheet.get('number',''),output.created_at]

def _root():
 root=Path(getattr(settings,'DATA_EXPORT_ROOT',Path(settings.MEDIA_ROOT)/'private_exports')).absolute()
 if root.is_symlink():raise ValidationError('Export storage is unavailable.')
 root.mkdir(parents=True,exist_ok=True,mode=0o700)
 return root.resolve()

def _path(job):
 root=_root();folder=root/str(job.owner_id)
 if folder.is_symlink():raise ValidationError('Export storage is unavailable.')
 folder.mkdir(mode=0o700,exist_ok=True)
 path=folder/(str(job.pk)+'.xlsx')
 if path.is_symlink():raise ValidationError('Export storage is unavailable.')
 return path

def _stream(actor,job,callback=None):
 digest=hashlib.sha256();count=0;size=0
 for identity,values in rows(actor,job):
  count+=1
  if count>MAX_ROWS:raise ValidationError('Export exceeds 50,000 rows. Select a smaller project or data section.')
  cells=[safe_cell(v) for v in values]
  encoded=json.dumps([identity,cells],ensure_ascii=False,separators=(',',':')).encode()
  size+=len(encoded)
  if size>MAX_TEXT_BYTES:raise ValidationError('Export text size exceeds 64 MiB. Select a smaller project or data section.')
  digest.update(encoded);digest.update(b'\n')
  if callback:callback(cells,count)
 return digest.hexdigest(),count

def _lease(token,job_id):
 now=timezone.now();until=now+timedelta(seconds=180)
 with transaction.atomic():
  if not DataExportWorkerLease.objects.filter(key='data-exports',token=token,expires_at__gt=now).update(expires_at=until):raise ValidationError('Worker lease expired; retry this export.')
  if not DataExportJob.objects.filter(pk=job_id,status='running',lease_token=token).update(lease_until=until):raise ValidationError('Export lease changed.')

def _workbook(actor,job,token):
 path=_path(job);temp=None
 book=Workbook(write_only=True);data=book.create_sheet('Data');data.append(HEADERS[job.section])
 def append(cells,count):
  if count%PAGE_SIZE==1:_lease(token,job.pk)
  data.append(cells)
 try:
  digest,count=_stream(actor,job,append)
  columns=book.create_sheet('Columns');columns.append(['Column','Meaning'])
  for heading in HEADERS[job.section]:columns.append([heading,'Saved, permission-scoped '+heading.lower()+'. Blank means not available.'])
  meta=book.create_sheet('Export');meta.append(['Property','Value'])
  for key,value in [('Schema version',SCHEMA_VERSION),('Section',LABELS[job.section]),('Requested at',job.created_at.isoformat()),('Prepared at',timezone.now().isoformat()),('Requester',actor.username),('Rows',count),('Source fingerprint',digest),('Scope','Current authorized records only; not a compliance approval'),('Formula safety','Text beginning = + - @ is prefixed with an apostrophe'),('Expiry',job.expires_at.isoformat())]:meta.append([key,safe_cell(value)])
  with NamedTemporaryFile(dir=path.parent,prefix='.export-',suffix='.tmp',delete=False) as f:temp=Path(f.name)
  os.chmod(temp,0o600);book.save(temp)
  if temp.stat().st_size>MAX_BYTES:raise ValidationError('Export exceeds the 30 MiB file limit. Narrow the scope.')
  _lease(token,job.pk)
  # Recheck a stable snapshot and role/grants before making an artifact ready.
  check,check_count=_stream(actor,job,lambda cells,n:_lease(token,job.pk) if n%PAGE_SIZE==1 else None)
  if (check,check_count)!=(digest,count):raise ValidationError('Source data changed during export. Retry to capture a consistent saved version.')
  sha=hashlib.sha256(temp.read_bytes()).hexdigest();size=temp.stat().st_size
  now=timezone.now();name=timezone.localtime(now).strftime('%Y_%m_%d_%H%M%S_')+job.section+'.xlsx'
  with transaction.atomic():
   current=DataExportJob.objects.select_for_update().get(pk=job.pk)
   if current.status!='running' or current.lease_token!=token or current.lease_until<=now:raise ValidationError('Export lease changed.')
   _scopes(actor,current);os.replace(temp,path);temp=None
   current.status='ready';current.row_count=count;current.source_digest=digest;current.file_name=name;current.sha256=sha;current.byte_count=size;current.completed_at=now;current.error='';current.lease_token=None;current.lease_until=None;current.save();_audit(actor,current,'completed')
 finally:
  if temp and temp.exists():temp.unlink()
  for sheet in book.worksheets:
   if not sheet.closed:sheet.close()
   writer=getattr(sheet,'_writer',None)
   if writer and Path(writer.out).is_file():writer.cleanup()
  book.close()

def process_next():
 now=timezone.now();token=uuid.uuid4()
 with transaction.atomic():
  lease,_=DataExportWorkerLease.objects.get_or_create(key='data-exports')
  if not DataExportWorkerLease.objects.filter(key='data-exports').filter(Q(expires_at__isnull=True)|Q(expires_at__lte=now)).update(token=token,expires_at=now+timedelta(seconds=180)):return False
  DataExportJob.objects.filter(status='running',lease_until__lte=now,attempts__gte=3).update(status='failed',error='Three interrupted attempts reached the retry limit. Request a fresh export.',lease_token=None,lease_until=None)
  job=DataExportJob.objects.filter(expires_at__gt=now,attempts__lt=3).filter(Q(status='queued')|Q(status='running',lease_until__lte=now)).order_by('created_at','pk').first()
  if not job:
   DataExportWorkerLease.objects.filter(key='data-exports',token=token).update(token=None,expires_at=None);return False
  job.status='running';job.lease_token=token;job.lease_until=now+timedelta(seconds=180);job.attempts=F('attempts')+1;job.error='';job.save();job.refresh_from_db()
 try:
  _workbook(_actor(job.owner),job,token)
 except (PermissionDenied,Http404,User.DoesNotExist):
  DataExportJob.objects.filter(pk=job.pk,lease_token=token,status='running').update(status='failed',error='Access changed. Check your current project access and request a new export.',lease_until=None,lease_token=None)
 except ValidationError as error:
  DataExportJob.objects.filter(pk=job.pk,lease_token=token,status='running').update(status='failed',error='; '.join(error.messages)[:240],lease_until=None,lease_token=None)
 except (OSError,ValueError,TypeError,KeyError):
  DataExportJob.objects.filter(pk=job.pk,lease_token=token,status='running').update(status='failed',error='Export could not finish. Check local storage or source data and retry.',lease_until=None,lease_token=None)
 finally:DataExportWorkerLease.objects.filter(key='data-exports',token=token).update(token=None,expires_at=None)
 return True

def retry(actor,job):
 actor=_actor(actor);_scopes(actor,job)
 if job.owner_id!=actor.pk:raise PermissionDenied()
 with transaction.atomic():
  User.objects.select_for_update().get(pk=actor.pk)
  current=DataExportJob.objects.select_for_update().get(pk=job.pk)
  if current.status in {'queued','running'}:return current
  if current.status!='failed' or current.attempts>=3 or current.expires_at<=timezone.now():raise ValidationError('This export cannot be retried; request a new export.')
  if DataExportJob.objects.filter(owner=actor,status__in=['queued','running'],expires_at__gt=timezone.now()).count()>=MAX_ACTIVE:raise ValidationError('Wait for an active export to finish.')
  current.status='queued';current.error='';current.save();_audit(actor,current,'retried');return current

def download_authorized(actor,job):
 actor=_actor(actor)
 if actor.pk!=job.owner_id:raise PermissionDenied('Only the requester may download this export.')
 job=DataExportJob.objects.get(pk=job.pk)
 if job.status!='ready' or job.expires_at<=timezone.now():raise ValidationError('This export is not ready or has expired. Request a fresh export.')
 digest,count=_stream(actor,job)
 if digest!=job.source_digest or count!=job.row_count:raise PermissionDenied('Source records or access changed. Request a new export.')
 path=_path(job)
 if not path.is_file() or path.stat().st_size!=job.byte_count or hashlib.sha256(path.read_bytes()).hexdigest()!=job.sha256:raise ValidationError('Export failed integrity verification. Request a fresh export.')
 _scopes(actor,job)
 _audit(actor,job,'downloaded');return path

def expire_exports():
 now=timezone.now();count=0
 for job in DataExportJob.objects.filter(expires_at__lte=now).exclude(status='expired').iterator(chunk_size=PAGE_SIZE):
  path=_path(job)
  if path.exists():path.unlink()
  DataExportJob.objects.filter(pk=job.pk).update(status='expired',lease_until=None,lease_token=None);count+=1
 return count
