"""Validated site-information preloads; preview first, then one atomic commit."""
import csv
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from io import StringIO
from itertools import islice
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Checklist,WorkAssignment,Project,Profile,AssignmentIntakeBatch
from .access import accessible_projects,project_role_guard,can_access_project,is_super_admin
from .template_service import validate_answer

MAX_CSV_BYTES=1024*1024
MAX_ROWS=200
BASE_COLUMNS={'project','engineer','site_id','latitude','longitude','description','answers_json','general_info'}
CONTEXT_COLUMNS={'quality_reviewer','workflow_type','governance_mode','asset_reference','coordinate_source','coordinate_crs','l2_reviewer','l3_approver','client_review_required','customer_reviewer','review_reason'}
BASE_COLUMNS|=CONTEXT_COLUMNS
SCALAR_TYPES={'text','textarea','number','date','select'}


def general_fields(definition):
    sections=definition.get('sections',[])
    chosen=[s for s in sections if s['id'] in {'general','site_information','site_info'} or s.get('purpose')=='general_info']
    if not chosen:
        chosen=[s for s in sections if any(f.get('system')=='site_id' for f in s['fields'])] or sections[:1]
    return {f['id']:f for s in chosen for f in s['fields'] if f['type'] in SCALAR_TYPES}


def validated_general_info(definition,values):
    if not isinstance(values,dict) or len(values)>300:
        raise ValidationError('General information must be a JSON object of field IDs and values.')
    fields=general_fields(definition)
    result={}
    for fid,value in values.items():
        field=fields.get(fid)
        if not field or field.get('system'):
            raise ValidationError(f'Unknown or read-only general-information field: {str(fid)[:80]}.')
        validate_answer(field,value)
        result[fid]=value
    return result


def survey_prefill_suggestions(checklist):
    """Deterministic development suggestions; never writes answers or site identity."""
    import math
    import re
    from datetime import datetime
    from django.conf import settings
    from .photo_metadata import metadata_is_current
    suggestions={}
    def candidate(kind,value,source,note='',conflict=False):
        suggestions[kind]={'suggested_value':value,'suggestion_source':source,'suggestion_note':note,'suggestion_conflict':conflict}
    owner=User.objects.get(pk=checklist.user_id)
    name=owner.get_full_name().strip()
    if not name:
        from .work_profile_models import WorkProfile
        name=WorkProfile.objects.filter(user=owner).values_list('display_name',flat=True).first() or ''
    if name.strip():candidate('surveyor',name.strip(),'assigned_account','Assigned surveyor account; manually editable during development.')
    if checklist.project.company_id:candidate('organization',checklist.project.company.name,'project_company','Organization from the project company account.')
    candidate('project',checklist.project.name,'project','Assigned project name.')
    captures=[];gps_values={};site_values={}
    pattern=re.compile(r'\s*site[ _-]*(?:id|code)\s*[:=#]\s*([A-Za-z0-9][A-Za-z0-9._-]{1,39})\s*',re.I)
    for photo in checklist.photo_evidence.all().order_by('pk'):
        metadata=photo.metadata if isinstance(photo.metadata,dict) else {}
        raw=metadata.get('captured_at')
        if isinstance(raw,str):
            captured=None
            for fmt in ['%Y:%m:%d %H:%M:%S','%Y-%m-%d %H:%M:%S']:
                try:captured=datetime.strptime(raw,fmt);break
                except ValueError:pass
            if not captured:
                try:captured=datetime.fromisoformat(raw)
                except ValueError:pass
            if captured:captures.append((captured,photo.pk))
        gps=metadata.get('gps')
        if isinstance(gps,dict):
            try:
                if type(gps.get('latitude')) is bool or type(gps.get('longitude')) is bool:raise ValueError()
                latitude,longitude=float(gps['latitude']),float(gps['longitude'])
                if math.isfinite(latitude) and math.isfinite(longitude) and -90<=latitude<=90 and -180<=longitude<=180:
                    gps_values.setdefault((round(latitude,6),round(longitude,6)),[]).append(photo.pk)
            except (ValueError,TypeError,KeyError,OverflowError):pass
        if metadata_is_current(photo,settings.OLLAMA_MODEL):
            for line in photo.analysis_metadata['visible_text']:
                match=pattern.fullmatch(line)
                if match:site_values.setdefault(match[1],[]).append(photo.pk)
    if captures:
        days={captured.date() for captured,_ in captures}
        if len(days)==1:
            # Compare local camera clock values without fabricating a timezone.
            earliest=min(captures,key=lambda item:item[0].replace(tzinfo=None))
            captured,pid=earliest
            note='Photo '+str(pid)+' capture details; earliest available capture time. Camera timezone is not inferred.'
            candidate('date',captured.date().isoformat(),'photo_exif',note)
            candidate('time',captured.strftime('%H:%M:%S'),'photo_exif',note)
            candidate('datetime',captured.isoformat(),'photo_exif',note)
        else:
            for kind in ['date','time','datetime']:candidate(kind,None,'photo_exif','Photos contain different capture dates. Choose the survey date and time manually.',True)
    if gps_values:
        if len(gps_values)==1:
            (latitude,longitude),ids=next(iter(gps_values.items()))
            note='Photo EXIF GPS, shared by photos '+', '.join(map(str,ids))+'. Coordinates only; region, city and survey datum are not inferred.'
            candidate('latitude',str(latitude),'photo_exif',note)
            candidate('longitude',str(longitude),'photo_exif',note)
            candidate('coordinates',f'{latitude:.6f}, {longitude:.6f}','photo_exif',note)
        else:
            for kind in ['latitude','longitude','coordinates']:candidate(kind,None,'photo_exif','Photo GPS positions differ. Choose the intended survey coordinates manually.',True)
    if site_values:
        if len(site_values)==1:
            value,ids=next(iter(site_values.items()))
            conflict=bool(checklist.site_id and checklist.site_id!=value)
            candidate('site',value,'photo_visible_text','Explicit Site ID/Code label read from photo '+', '.join(map(str,sorted(set(ids))))+'. Verify the original image. Assigned site identity remains unchanged.',conflict)
        else:candidate('site',None,'photo_visible_text','Photos show conflicting explicit Site IDs. Assigned site identity remains unchanged.',True)
    return suggestions


def site_information_fields(checklist):
    from .template_views import field_is_locked
    import re
    answers=(checklist.answer_data or {}).get('custom',{})
    suggestions=survey_prefill_suggestions(checklist)
    from .independent_workflow import is_frozen
    editable=checklist.status in {Checklist.Status.DRAFT,Checklist.Status.REJECTED,Checklist.Status.PARTIAL} and not is_frozen(checklist)
    aliases={
        'surveyor':{'surveyorname','surveyorfullname','surveyedby','surveyor','surveyengineername','engineername','inspectorname'},
        'organization':{'surveyororganizationname','surveyororganisationname','surveyororganization','surveyororganisation','organizationname','organisationname','companyname','employername','employer','surveycompanyname'},
        'project':{'projectname'},'date':{'sitesurveydate','surveydate','dateofsurvey'},'time':{'sitesurveytime','surveytime','timeofsurvey'},
        'datetime':{'sitesurveydatetime','surveydatetime','dateandtimeofsurvey'},
        'latitude':{'latitude','sitelatitude','gpslatitude','lat'},'longitude':{'longitude','sitelongitude','gpslongitude','lon'},
        'coordinates':{'coordinates','gpscoordinates','sitecoordinates','sitelocationregioncitycoordinates','sitelocationcoordinates'},'site':{'siteid','sitecode','siteidentifier'}}
    rows=[]
    for fid,field in general_fields(checklist.schema_snapshot).items():
        keys={re.sub(r'[^a-z0-9]','',str(value).lower()) for value in [fid,field['label']]}
        kind=next((kind for kind,labels in aliases.items() if keys&labels),None)
        proposal=suggestions.get(kind,{})
        stored=checklist.site_id if field.get('system')=='site_id' else answers.get(fid,'')
        locked=bool(field.get('system')) or field_is_locked(checklist,fid)
        row={**field,'stored_value':stored,'value':stored,'locked':locked,'prefilled':False,'suggested_value':None,'suggestion_source':'','suggestion_note':'','suggestion_conflict':False,**proposal}
        value=proposal.get('suggested_value')
        if value is not None and not proposal.get('suggestion_conflict') and not locked and editable and fid not in answers:
            try:validate_answer(field,value)
            except ValidationError:
                row['suggestion_note']=(row['suggestion_note']+' This value does not fit the checklist field; enter a valid value manually.').strip()
            else:row['value']=value;row['prefilled']=True
        rows.append(row)
    return rows


def schema_fingerprint(project):
    template=project.checklist_template
    if not template or not template.published:
        raise ValidationError('A published project checklist is required.')
    return hashlib.sha256(json.dumps({'template_id':template.pk,'definition':template.definition,'industry':project.industry},sort_keys=True,separators=(',',':')).encode()).hexdigest()


@transaction.atomic
def create_assignment(actor,data,source):
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot assign engineering tasks.')
    project=data['project']
    if project.review_layers in (3,4):
        data=dict(data)
        required=project.review_layers==4
        supplied=data.get('client_review_required')
        if supplied and (supplied=='required')!=required:
            raise ValidationError('Client approval routing is fixed by the project workflow.')
        if not required and data.get('customer_reviewer'):
            raise ValidationError('A three-layer task cannot have a Client approval stage.')
        if required and not data.get('customer_reviewer'):
            raise ValidationError('Assign the project Client reviewer for this four-layer task.')
        data['governance_mode']=Checklist.GovernanceMode.INDEPENDENT
        data['client_review_required']='required' if required else 'not_required'
        data['l2_reviewer']=data.get('l2_reviewer') or data.get('quality_reviewer')
        if not data.get('l2_reviewer') or not data.get('l3_approver'):
            raise ValidationError('Assign a Quality Engineer and Team Lead for the project review workflow.')
        data['review_reason']=data.get('review_reason') or f'Project-selected {project.review_layers}-layer approval workflow.'
    engineer=data['engineer']
    project_role_guard(actor,project,{Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN})
    if not engineer.is_active or engineer.profile.role!=Profile.Roles.ENGINEER or not can_access_project(engineer,project):
        raise PermissionDenied('Engineer membership changed.')
    quality=data.get('l2_reviewer') if data.get('governance_mode')=='independent' else data.get('quality_reviewer')
    from .quality_workflow import require_quality_reviewer
    require_quality_reviewer(project.pk,quality,engineer.pk)
    answers=validated_general_info(project.checklist_template.definition,data.get('general_info',{}))
    metadata={'source':source,'created_by':actor.pk,'created_at':timezone.now().isoformat(),'prefilled_field_ids':list(answers)}
    from .industry_service import industry_family
    checklist=Checklist.objects.create(user=engineer,project=project,site_id=data['site_id'],answer_data={'custom':answers} if answers else {},intake_metadata=metadata,quality_reviewer=quality,workflow_type=data.get('workflow_type') or (Checklist.WorkflowType.CONSTRUCTION_INSPECTION if industry_family(project)==Project.Industry.CONSTRUCTION else Checklist.WorkflowType.TELECOM_SURVEY),governance_mode=data.get('governance_mode') or Checklist.GovernanceMode.LEGACY,asset_reference=data.get('asset_reference',''),coordinate_reference={'source':data.get('coordinate_source',''),'crs':data.get('coordinate_crs','')})
    if checklist.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
        from .independent_workflow import configure_policy
        configure_policy(actor,checklist,data['l2_reviewer'],data['l3_approver'],data['review_reason'],customer_reviewer=data.get('customer_reviewer'),customer_required=data.get('client_review_required')=='required',enable_route=project.review_layers in (3,4))
    assignment=WorkAssignment.objects.create(project=project,assigned_to=engineer,assigned_by=actor,site_id=data['site_id'],latitude=data['latitude'],longitude=data['longitude'],description=data['description'],checklist=checklist)
    from .governance_views import audit
    audit(actor,'task_assigned',project,assignment_id=assignment.pk,checklist_id=checklist.pk,engineer_id=engineer.pk,site_id=assignment.site_id,preload_fields=list(answers),source=source)
    return assignment


def resolve_row(actor,row,default_project=''):
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot prepare engineering task assignments.')
    from .governance_forms import AssignmentForm
    project_value=str(row.get('project') or default_project).strip()
    scope=accessible_projects(actor)
    project=scope.filter(pk=int(project_value)).first() if project_value.isascii() and project_value.isdigit() else scope.filter(name=project_value).first()
    if not project:
        raise ValidationError('Choose an accessible project ID or exact project name.')
    project_role_guard(actor,project,{Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN})
    engineer_value=str(row.get('engineer','')).strip()
    engineer=User.objects.filter(username=engineer_value).first()
    if not engineer and engineer_value.isascii() and engineer_value.isdigit():
        engineer=User.objects.filter(pk=int(engineer_value)).first()
    if not engineer:
        raise ValidationError('Engineer must be an existing assigned username or user ID.')
    values={}
    for column in ('answers_json','general_info'):
        if row.get(column):
            try:
                parsed=json.loads(row[column]) if isinstance(row[column],str) else row[column]
            except (ValueError,TypeError):
                raise ValidationError(f'{column} must contain valid JSON.')
            if not isinstance(parsed,dict):
                raise ValidationError(f'{column} must be a JSON object.')
            if set(values)&set(parsed):
                raise ValidationError('A preload field was supplied more than once.')
            values.update(parsed)
    for key,value in row.items():
        if key not in BASE_COLUMNS and value not in ('',None):
            fid=key[6:] if key.startswith('field:') else key
            if fid in values:
                raise ValidationError('A preload field was supplied more than once.')
            values[fid]=value
    context={key:row.get(key,'') for key in CONTEXT_COLUMNS}
    for key in ['quality_reviewer','l2_reviewer','l3_approver','customer_reviewer']:
        value=str(context[key]).strip()
        if value and not value.isdigit():
            reviewer=User.objects.filter(username=value).first()
            context[key]=reviewer.pk if reviewer else value
    form=AssignmentForm({**context,'project':project.pk,'engineer':engineer.pk,'site_id':row.get('site_id',''),'latitude':row.get('latitude',''),'longitude':row.get('longitude',''),'description':row.get('description',''),'general_info':json.dumps(values)},actor=actor)
    if not form.is_valid():
        raise ValidationError([f'{key}: {message}' for key,messages in form.errors.items() for message in messages])
    data=form.cleaned_data
    normalized_context={key:(getattr(data.get(key),'pk',data.get(key)) or '') for key in CONTEXT_COLUMNS}
    return data,{**normalized_context,'project_id':project.pk,'project_name':project.name,'engineer_id':engineer.pk,'engineer_name':engineer.username,'site_id':data['site_id'],'latitude':str(data['latitude']),'longitude':str(data['longitude']),'description':data['description'],'general_info':data['general_info']}


def preview_csv(actor,upload,default_project=''):
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot preview engineering task assignments.')
    raw=upload.read(MAX_CSV_BYTES+1)
    if len(raw)>MAX_CSV_BYTES:
        raise ValidationError('CSV files must be 1 MiB or smaller.')
    try:
        text=raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValidationError('Use a UTF-8 CSV file.')
    reader=csv.DictReader(StringIO(text,newline=''),strict=True)
    try:
        headers=reader.fieldnames
        source_rows=list(islice(reader,MAX_ROWS+1))
    except csv.Error:
        raise ValidationError('CSV is malformed or contains an overlong cell.')
    if not headers or len(headers)>320 or len(set(headers))!=len(headers) or any(not h or h.strip()!=h for h in headers):
        raise ValidationError('CSV requires unique, non-empty header names without surrounding spaces.')
    required={'engineer','site_id','latitude','longitude','description'}
    if not required.issubset(headers) or 'project' not in headers and not default_project:
        raise ValidationError('Required CSV columns: project, engineer, site_id, latitude, longitude, description.')
    rows=[]
    errors=[]
    fingerprints={}
    seen=set()
    for number,row in enumerate(source_rows,start=2):
        if number>MAX_ROWS+1:
            raise ValidationError('Preview at most 200 CSV rows per batch.')
        if None in row or any(v is None for v in row.values()):
            errors.append({'row':number,'message':'The number of columns differs from the header.'})
            continue
        try:
            data,normalized=resolve_row(actor,row,default_project)
            fields=general_fields(data['project'].checklist_template.definition)
            unknown=[h for h in headers if h not in BASE_COLUMNS and (h[6:] if h.startswith('field:') else h) not in fields]
            if unknown:
                raise ValidationError('Unknown general-information CSV columns: '+', '.join(unknown))
            if normalized['site_id'] in seen:
                raise ValidationError('A site ID is repeated within this batch.')
            seen.add(normalized['site_id'])
            fingerprints[str(data['project'].pk)]=schema_fingerprint(data['project'])
            normalized['row_number']=number
            rows.append(normalized)
        except ValidationError as exc:
            errors.append({'row':number,'message':'; '.join(exc.messages)})
        except PermissionDenied:
            errors.append({'row':number,'message':'This row is outside your assignment authority.'})
    if not rows and not errors:
        raise ValidationError('CSV contains no site rows.')
    return AssignmentIntakeBatch.objects.create(requested_by=actor,source_filename=upload.name[:255],source_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,errors=errors,schema_fingerprints=fingerprints,status='invalid' if errors else 'preview',expires_at=timezone.now()+timedelta(hours=1))


@transaction.atomic
def commit_batch(actor,batch):
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot commit engineering task assignments.')
    from .governance_views import lock_governance
    lock_governance(actor)
    batch=AssignmentIntakeBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.requested_by_id!=actor.pk:
        raise PermissionDenied('Only the preview creator can commit this batch.')
    if batch.status=='committed':
        return batch.result_ids
    if batch.errors or batch.status!='preview' or batch.expires_at<=timezone.now():
        raise ValidationError('Preview is invalid or expired; upload and validate it again.')
    validated=[]
    for row in batch.rows:
        raw={**{key:row.get(key,'') for key in CONTEXT_COLUMNS},'project':row['project_id'],'engineer':row['engineer_name'],'site_id':row['site_id'],'latitude':row['latitude'],'longitude':row['longitude'],'description':row['description'],'general_info':row['general_info']}
        data,_=resolve_row(actor,raw)
        if data['engineer'].pk!=row['engineer_id']:
            raise ValidationError('An Engineer account changed after preview; preview again.')
        if schema_fingerprint(data['project'])!=batch.schema_fingerprints[str(data['project'].pk)]:
            raise ValidationError('A project checklist changed after preview; create a new preview.')
        validated.append(data)
    source={'kind':'bulk_csv','batch_id':batch.pk,'filename':batch.source_filename,'sha256':batch.source_sha256}
    results=[create_assignment(actor,data,source).pk for data in validated]
    batch.status='committed'
    batch.result_ids=results
    batch.committed_at=timezone.now()
    batch.save(update_fields=['status','result_ids','committed_at'])
    from .governance_views import audit
    audit(actor,'assignment_batch_committed',batch_id=batch.pk,assignment_ids=results,source_sha256=batch.source_sha256)
    return results
