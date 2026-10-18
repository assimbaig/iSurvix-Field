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


def site_information_fields(checklist):
    from .template_views import field_is_locked
    answers=(checklist.answer_data or {}).get('custom',{})
    return [{**f,'value':checklist.site_id if f.get('system')=='site_id' else answers.get(fid,''),'locked':bool(f.get('system')) or field_is_locked(checklist,fid)} for fid,f in general_fields(checklist.schema_snapshot).items()]


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
    engineer=data['engineer']
    project_role_guard(actor,project,{Profile.Roles.TEAM_LEAD,Profile.Roles.ADMIN})
    if not engineer.is_active or engineer.profile.role!=Profile.Roles.ENGINEER or not can_access_project(engineer,project):
        raise PermissionDenied('Engineer membership changed.')
    quality=data.get('l2_reviewer') if data.get('governance_mode')=='independent' else data.get('quality_reviewer')
    from .quality_workflow import require_quality_reviewer
    require_quality_reviewer(project.pk,quality,engineer.pk)
    answers=validated_general_info(project.checklist_template.definition,data.get('general_info',{}))
    metadata={'source':source,'created_by':actor.pk,'created_at':timezone.now().isoformat(),'prefilled_field_ids':list(answers)}
    checklist=Checklist.objects.create(user=engineer,project=project,site_id=data['site_id'],answer_data={'custom':answers} if answers else {},intake_metadata=metadata,quality_reviewer=quality,workflow_type=data.get('workflow_type') or (Checklist.WorkflowType.CONSTRUCTION_INSPECTION if project.industry==Project.Industry.CONSTRUCTION else Checklist.WorkflowType.TELECOM_SURVEY),governance_mode=data.get('governance_mode') or Checklist.GovernanceMode.LEGACY,asset_reference=data.get('asset_reference',''),coordinate_reference={'source':data.get('coordinate_source',''),'crs':data.get('coordinate_crs','')})
    if checklist.governance_mode==Checklist.GovernanceMode.INDEPENDENT:
        from .independent_workflow import configure_policy
        configure_policy(actor,checklist,data['l2_reviewer'],data['l3_approver'],data['review_reason'],customer_reviewer=data.get('customer_reviewer'),customer_required=data.get('client_review_required')=='required')
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
