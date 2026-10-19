"""Scoped draft authoring and atomic, review-before-create workbook intake."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import hmac
import json
import re
from pathlib import PurePath
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .access import company_id_for, is_super_admin, role_for
from .models import ChecklistImportBatch, ChecklistTemplate, Profile
from .standard_checklist_service import permitted_industries, standard_metadata, wizard_metadata
from .template_service import validate_definition
from .template_views import template_scope

WORKFLOWS = {'telecom_survey': 'telecom', 'telecom_inspection': 'telecom',
             'construction_inspection': 'construction'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def guard(actor, write=False):
    allowed=permitted_industries(actor)&set(WORKFLOWS.values())
    if not allowed:
        raise PermissionDenied('No supported checklist workflow is configured for your assigned industry.')
    if write and (is_super_admin(actor) or role_for(actor)!=Profile.Roles.ADMIN):
        raise PermissionDenied('Only a scoped Project Admin can create operational checklist drafts.')
    return allowed


def identity(actor, industry, workflow):
    if industry not in guard(actor, True):
        raise PermissionDenied('This checklist is outside your assigned industry.')
    if not isinstance(workflow,str) or WORKFLOWS.get(workflow)!=industry:
        raise ValidationError('Choose a workflow belonging to the selected industry.')
    return {'version':1,'industry':industry,'workflow_type':workflow}


def source_identity(template, actor):
    metadata=wizard_metadata(template.definition) or standard_metadata(template.definition)
    if metadata:
        identity(actor,metadata['industry'],metadata['workflow_type'])
        return {key:metadata[key] for key in ('industry','workflow_type')}
    # Legacy templates have no module marker. Infer only from scoped usage.
    from .access import accessible_projects
    from django.db.models import Q
    projects=accessible_projects(actor).filter(Q(checklist_template=template)|Q(checklists__checklist_template=template)).distinct()
    from .industry_service import industry_family
    industries={industry_family(code) for code in projects.values_list('industry',flat=True)}
    allowed=guard(actor,True)
    if not industries:industries=allowed
    if len(industries)!=1 or not industries<=allowed:
        raise ValidationError('This legacy source has no unambiguous industry. Export or create a scoped draft first.')
    industry=next(iter(industries))
    workflows=set(template.checklists.filter(project__in=projects).values_list('workflow_type',flat=True))
    workflows={value for value in workflows if value in WORKFLOWS}
    if len(workflows)>1:
        raise ValidationError('This legacy source spans multiple workflows. Choose a module-specific standard.')
    return {'industry':industry,'workflow_type':next(iter(workflows), 'construction_inspection' if industry=='construction' else 'telecom_survey')}


def valid_name(value):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>160:
        raise ValidationError('Provide a checklist name of at most 160 characters.')
    return value.strip()


def create_blank(actor,name,industry,workflow):
    from .governance_views import lock_governance,audit
    with transaction.atomic():
        lock_governance(actor)
        context=identity(actor,industry,workflow)
        definition={'title':valid_name(name),'wizard_context':context,'sections':[
            {'id':'general','title':'General information','fields':[
                {'id':'site_id','label':'Site ID','type':'text','system':'site_id','required':True}]}]}
        template=ChecklistTemplate.objects.create(name=valid_name(name),definition=definition,created_by=actor)
        audit(actor,'checklist_wizard_create',template_id=template.pk)
        return template


def replicate(actor,source_id,name):
    from .governance_views import lock_governance,audit
    with transaction.atomic():
        lock_governance(actor);guard(actor,True)
        source=get_object_or_404(template_scope(actor),pk=source_id)
        context=source_identity(source,actor)
        definition=deepcopy(source.definition)
        definition['wizard_context']=identity(actor,context['industry'],context['workflow_type'])
        template=ChecklistTemplate.objects.create(name=valid_name(name),definition=definition,created_by=actor,
            client_left_name=source.client_left_name,client_right_name=source.client_right_name,
            client_left_logo=source.client_left_logo.name,client_right_logo=source.client_right_logo.name)
        audit(actor,'checklist_wizard_replicate',template_id=template.pk,source_id=source.pk)
        return template


def preview_import(actor,upload):
    from .checklist_workbook import MAX_BYTES,parse_workbook
    from .governance_views import lock_governance,audit
    guard(actor,True)
    if not upload or not upload.name.lower().endswith('.xlsx') or upload.size>MAX_BYTES:
        raise ValidationError('Choose an .xlsx workbook up to 5 MB.')
    raw=upload.read(MAX_BYTES+1)
    parsed=parse_workbook(raw)
    with transaction.atomic():
        lock_governance(actor);guard(actor,True)
        for item in parsed['checklists']:
            item['name']=valid_name(item['name'])
            context=identity(actor,item['industry'],item['workflow_type'])
            item['definition']['wizard_context']=context
            validate_definition(item['definition'])
        payload={'checklists':parsed['checklists'],'warnings':parsed.get('warnings',[])}
        batch=ChecklistImportBatch.objects.create(created_by=actor,company_id=company_id_for(actor),
            filename=PurePath(upload.name.replace('\\','/')).name[:255],upload_sha256=parsed['sha256'],
            payload=payload,payload_digest=digest(payload),expires_at=timezone.now()+timedelta(minutes=30))
        audit(actor,'checklist_import_preview',import_id=str(batch.pk),count=len(payload['checklists']),sha256=batch.upload_sha256)
        return batch


def get_batch(actor,batch_id):
    guard(actor,True)
    try:return get_object_or_404(ChecklistImportBatch,pk=batch_id,created_by=actor,company_id=company_id_for(actor))
    except (ValidationError,ValueError,TypeError):
        from django.http import Http404
        raise Http404('Import preview not found.')


def commit_import(actor,batch_id,expected_digest):
    from .governance_views import lock_governance,audit
    with transaction.atomic():
        lock_governance(actor);guard(actor,True)
        batch=get_batch(actor,batch_id)
        batch=ChecklistImportBatch.objects.select_for_update().get(pk=batch.pk)
        if (not isinstance(expected_digest,str) or not re.fullmatch('[0-9a-f]{64}',expected_digest) or
            not hmac.compare_digest(batch.payload_digest,expected_digest) or
            not hmac.compare_digest(batch.payload_digest,digest(batch.payload))):
            raise ValidationError('The import preview changed. Validate the workbook again.')
        for item in batch.payload['checklists']:
            context=identity(actor,item['industry'],item['workflow_type'])
            if item['definition'].get('wizard_context')!=context:
                raise ValidationError('The preview industry or workflow changed. Validate the workbook again.')
            valid_name(item['name']);validate_definition(item['definition'])
        if batch.committed_at:
            if template_scope(actor).filter(pk__in=batch.created_template_ids).count()!=len(batch.created_template_ids):
                raise PermissionDenied('The created drafts are no longer in your permitted scope.')
            return batch
        if batch.expires_at<=timezone.now():
            raise ValidationError('This import preview expired. Validate the workbook again.')
        templates=[ChecklistTemplate.objects.create(name=item['name'],definition=deepcopy(item['definition']),created_by=actor)
                   for item in batch.payload['checklists']]
        batch.created_template_ids=[item.pk for item in templates];batch.committed_at=timezone.now()
        batch.save(update_fields=['created_template_ids','committed_at'])
        audit(actor,'checklist_import_commit',import_id=str(batch.pk),template_ids=batch.created_template_ids)
        return batch


def preview_context(batch):
    checklists=[]
    for item in batch.payload['checklists']:
        fields=[field for section in item['definition']['sections'] for field in section['fields']]
        checklists.append({**{key:item[key] for key in ('key','name','industry','workflow_type')},
            'section_count':len(item['definition']['sections']),'field_count':len(fields),
            'conditions_summary':f"{sum(bool(f.get('required')) for f in fields)} required; "
                f"{sum(bool(f.get('photo_required')) for f in fields)} photo requirements; "
                f"{sum('evidence_rules' in f for f in fields)} evidence rules"})
    return {'id':str(batch.pk),'digest':batch.payload_digest,'filename':batch.filename,'expires_at':batch.expires_at,
            'checklists':checklists,'warnings':batch.payload.get('warnings',[]),'committed':bool(batch.committed_at),
            'template_ids':batch.created_template_ids}


def example_records(industry='telecom'):
    if industry=='construction':
        from .standard_checklists import build_standard
        return [{'key':'construction_activities','name':'Construction activity checklist - editable starter',
                 'industry':'construction','workflow_type':'construction_inspection',
                 'definition':build_standard('construction_inspection_all')}]
    fields=[{'id':'site_id','label':'Site ID','type':'text','system':'site_id','required':True},
            {'id':'survey_date','label':'Survey date','type':'date','required':True},
            {'id':'notes','label':'Scope and notes','type':'textarea','required':False},
            {'id':'height','label':'Measured height (m)','type':'number','required':False},
            {'id':'asset_type','label':'Asset type','type':'select','required':True,'options':['Tower','Cabinet','Other']},
            {'id':'condition','label':'Visible tower condition','type':'inspection','required':True,'photo_required':True,
             'evidence_rules':{'version':1,'required_subjects':['tower'],'any_subjects':['steel','antenna'],
              'required_text':['SITE'],'forbidden_subjects':['indoor room'],'expected_site_id':'DEMO-SITE',
              'require_readable_text':True,'require_qr':True,'require_gps':True,'require_capture_time':True,
              'min_photos':1,'minimum_quality':'clear','notes':'Example only: adjust every rule to the actual checkpoint before use.'}},
            {'id':'test_records','label':'Repeatable test reports','type':'table','required':False,'columns':[
                {'id':'report_id','label':'Report reference'},{'id':'date','label':'Test date'},
                {'id':'location','label':'Activity / location'},{'id':'criteria','label':'Approved criteria reference'},
                {'id':'result','label':'Actual result and units'},{'id':'retest','label':'Retest / corrective action'}]},
            {'id':'evidence','label':'Supporting photo','type':'photo','required':False}]
    return [{'key':'example_survey','name':'EXAMPLE - Telecom survey (replace before use)','industry':'telecom',
             'workflow_type':'telecom_survey','definition':{'title':'Example survey','sections':[{'id':'general','title':'Example survey checks','fields':fields}]}},
            {'key':'example_inspection','name':'EXAMPLE - Telecom inspection (replace before use)','industry':'telecom',
             'workflow_type':'telecom_inspection','definition':{'title':'Example inspection','sections':[
                 {'id':'installation','title':'Example installation','fields':[{'id':'workmanship','label':'Installation workmanship','type':'inspection','required':True}]}]}}]
