"""Saved site facts for Engineer capture, separate from photographic evidence."""
from copy import deepcopy
from decimal import Decimal,InvalidOperation
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Checklist,WorkAssignment
from .template_service import validate_answer
from .field_intake_service import SCALAR_TYPES,survey_prefill_suggestions


CONTEXT_KEY='general_information_context'
CONTEXT_VERSION=1
GENERAL_SECTIONS={'general','general_info','general_information','site_info','site_information'}
BASICS={'site_name':('Site name',200),'address':('Site address',1000),'city':('City',200),'region':('Region',200)}
LABELS={'site_id':'Site ID','project':'Project','engineer':'Assigned Engineer','engineer_email':'Engineer email',
    'company':'Company / organization','client':'Client','assigned_latitude':'Assigned latitude','assigned_longitude':'Assigned longitude'}
ALIASES={
    'engineer':{'surveyorname','surveyorfullname','surveyedby','surveyor','surveyengineername','engineername','inspectorname'},
    'engineer_email':{'surveyoremail','surveyoremailid','engineeremail','engineeremailid','inspectoremail','inspectoremailid','surveyorcontactemail'},
    'company':{'surveyororganizationname','surveyororganisationname','surveyororganization','surveyororganisation',
        'organization','organisation','organizationname','organisationname','company','companyname','employername','employer','surveycompanyname'},
    'project':{'projectname'},'client':{'clientname','customername','clientorganization','clientorganisation','clientorganizationname'},
    'site_id':{'siteid','sitecode','siteidentifier'},
    'date':{'sitesurveydate','surveydate','dateofsurvey'},'time':{'sitesurveytime','surveytime','timeofsurvey'},
    'datetime':{'sitesurveydatetime','surveydatetime','dateandtimeofsurvey'},
    'latitude':{'latitude','sitelatitude','gpslatitude','lat'},'longitude':{'longitude','sitelongitude','gpslongitude','lon'},
    'coordinates':{'coordinates','gpscoordinates','sitecoordinates','sitelocationregioncitycoordinates','sitelocationcoordinates'},
    'site_name':{'sitename'},'address':{'address','siteaddress'},'city':{'city','sitecity'},'region':{'region','siteregion'},
}


def approved_fields(schema):
    return [(section,field) for section in schema.get('sections',[])
        if section.get('id') in GENERAL_SECTIONS or section.get('purpose')=='general_info'
        for field in section.get('fields',[]) if field.get('type') in SCALAR_TYPES]


def kind_for(field):
    if field.get('system')=='site_id':return 'site_id'
    keys={re.sub(r'[^a-z0-9]','',str(value).lower()) for value in (field['id'],field['label'])}
    return next((kind for kind,aliases in ALIASES.items() if keys&aliases),None)


def live_context(c):
    from django.contrib.auth.models import User
    owner=User.objects.get(pk=c.user_id)
    name=owner.get_full_name().strip()
    if not name:
        from .work_profile_models import WorkProfile
        name=WorkProfile.objects.filter(user_id=owner.pk).values_list('display_name',flat=True).first() or owner.get_username()
    company=c.project.company.name if c.project.company_id else ''
    if not company and c.project.administrator_id:
        profile=getattr(c.project.administrator,'profile',None)
        if profile and profile.company_id:company=profile.company.name
    client=c.project.client_organization.name if c.project.client_organization_id else ''
    if not client:
        policy=getattr(c,'review_policy',None)
        customer=policy.customer_reviewer if policy and policy.customer_reviewer_id else None
        if customer:client=customer.get_full_name().strip() or customer.get_username()
    assignment=WorkAssignment.objects.filter(checklist_id=c.pk).first()
    context={'site_id':c.site_id,'project':c.project.name,'engineer':name,'engineer_email':owner.email or '',
        'company':company,'client':client,'assigned_latitude':'','assigned_longitude':''}
    if assignment:
        for key,value,limit in [('assigned_latitude',assignment.latitude,90),('assigned_longitude',assignment.longitude,180)]:
            try:
                number=Decimal(str(value))
                if number.is_finite() and -limit<=number<=limit:context[key]=str(value)
            except (InvalidOperation,ValueError,TypeError):pass
    return context


def frozen_context(snapshot):
    saved=snapshot.get('intake',{}).get(CONTEXT_KEY,{})
    if isinstance(saved,dict) and saved.get('version')==CONTEXT_VERSION:
        return {key:str(saved.get(key,'')) for key in LABELS}
    # Older immutable submissions did not capture account display names. Do not
    # substitute today's profile or manufacture a historical identity.
    return {**dict.fromkeys(LABELS,''),'site_id':snapshot.get('site_id',''),
        'project':snapshot.get('project',''),'company':snapshot.get('company','')}


def describe(c,flags,revision=None):
    from .survey_processing import digest
    from .template_views import field_is_locked
    frozen=not flags['can_edit'] and revision is not None
    snapshot=revision.snapshot if frozen else None
    schema=snapshot.get('schema',{}) if frozen else c.schema_snapshot
    raw_answers=snapshot.get('answers',{}) if frozen else c.answer_data or {}
    answers=raw_answers.get('custom',{})
    metadata=snapshot.get('intake',{}) if frozen else c.intake_metadata or {}
    basic=metadata.get('site_information',{})
    if not isinstance(basic,dict):basic={}
    provenance=metadata.get('general_information_sources',{})
    if not isinstance(provenance,dict):provenance={}
    context=frozen_context(snapshot) if frozen else live_context(c)
    suggestions={} if frozen else survey_prefill_suggestions(c)
    # Task coordinates are recorded facts; missing task coordinates may use
    # existing unambiguous EXIF suggestions. Never create a location/date.
    for kind,key in [('latitude','assigned_latitude'),('longitude','assigned_longitude')]:
        if context[key]:suggestions[kind]={'suggested_value':context[key],'suggestion_source':'assigned_task','suggestion_note':'Recorded task coordinate.'}
    if context['assigned_latitude'] and context['assigned_longitude']:
        suggestions['coordinates']={'suggested_value':context['assigned_latitude']+', '+context['assigned_longitude'],
            'suggestion_source':'assigned_task','suggestion_note':'Recorded task coordinates; datum is not inferred.'}
    rows=[]
    for key,(label,maximum) in BASICS.items():
        value=basic.get(key,'')
        if not isinstance(value,str):value=''
        rows.append({'id':key,'scope':'site','label':label,'type':'text','value':value,'stored_value':value,
            'required':False,'editable':flags['can_edit'],'locked':not flags['can_edit'],'prefilled':False,
            'source':'frozen_submission' if frozen and key in basic else 'saved_site_data' if key in basic else 'not_recorded',
            'source_note':provenance.get('site:'+key,{}).get('note',''),'suggestion_conflict':False,'options':[],'unit':'','max_length':maximum,'section_id':''})
    for section,field in approved_fields(schema):
        ident=field['id'];kind=kind_for(field)
        canonical=kind in LABELS
        locked=field_is_locked(c,ident)
        stored=answers.get(ident,'')
        recorded_source=provenance.get(ident,{})
        if not isinstance(recorded_source,dict):recorded_source={}
        row={**field,'scope':'general','stored_value':stored,'value':stored,'section_id':section['id'],
            'editable':bool(flags['can_edit'] and not locked and not field.get('system')),
            'locked':bool(locked or field.get('system') or not flags['can_edit']),
            'prefilled':False,'source':'frozen_submission' if frozen and ident in answers else 'saved_answer' if ident in answers else 'not_recorded',
            'source_note':'','suggestion_conflict':False,'options':field.get('options',[]),'unit':field.get('unit',''),
            'max_length':10000}
        if ident in answers and recorded_source:
            row['source']=recorded_source.get('source',row['source'])
            row['source_note']=recorded_source.get('note','')
        proposal={}
        if canonical:
            proposal={'suggested_value':context[kind],'suggestion_source':'frozen_submission' if frozen else
                'assigned_account' if kind in {'engineer','engineer_email'} else 'assigned_task',
                'suggestion_note':'Assigned system context.' if field.get('system') else
                    'Suggested from the assigned account/project; the recorded site value remains editable during development.'}
        elif kind in BASICS and kind in basic:
            proposal={'suggested_value':basic[kind],'suggestion_source':'saved_site_data','suggestion_note':'Recorded site information.'}
        elif kind in suggestions:proposal=suggestions[kind]
        if ident not in answers:row['source_note']=proposal.get('suggestion_note','')
        row['suggestion_conflict']=bool(proposal.get('suggestion_conflict'))
        candidate=proposal.get('suggested_value')
        if ident not in answers and candidate not in (None,'') and not row['suggestion_conflict'] and not locked:
            try:validate_answer(field,candidate)
            except ValidationError:row['source_note']='The recorded source does not fit this approved field. Review it manually.'
            else:
                row.update(value=candidate,prefilled=not frozen,source=proposal.get('suggestion_source','not_recorded'))
        rows.append(row)
    signature=digest({'schema':[(s['id'],f) for s,f in approved_fields(schema)],
        'answers':{f['id']:answers[f['id']] for _,f in approved_fields(schema) if f['id'] in answers},
        'site_information':{key:basic[key] for key in BASICS if key in basic},'context':context,
        'locked':[row['id'] for row in rows if row['scope']=='general' and field_is_locked(c,row['id'])]})
    return {'digest':signature,'can_edit':flags['can_edit'],'read_only':not flags['can_edit'],'frozen':frozen,
        'context':[{'id':key,'label':label,'value':context[key],
            'source':'frozen_submission' if frozen and context[key] else 'assigned_system' if context[key] else 'not_recorded'} for key,label in LABELS.items()],
        'fields':rows}


def materialize_missing(c):
    """Explicit Save/Submit only: store the factual prefills actually displayed."""
    data=deepcopy(c.answer_data or {});answers=data.setdefault('custom',{})
    added=[]
    provenance=deepcopy((c.intake_metadata or {}).get('general_information_sources',{}))
    if not isinstance(provenance,dict):provenance={}
    for row in describe(c,{'can_edit':True})['fields']:
        if row['scope']=='general' and row['id'] not in answers and row['prefilled']:
            answers[row['id']]=row['value'];added.append(row['id'])
            provenance[row['id']]={'source':row['source'],'note':row['source_note'],'by':c.user_id}
    if added:c.answer_data=data
    if added:c.intake_metadata={**(c.intake_metadata or {}),'general_information_sources':provenance}
    return added


def freeze_for_submission(c):
    added=materialize_missing(c)
    c.intake_metadata={**(c.intake_metadata or {}),CONTEXT_KEY:{'version':CONTEXT_VERSION,**live_context(c)}}
    c.save(update_fields=['answer_data','intake_metadata','updated_at'])
    return added


@transaction.atomic
def save(request,checklist_id,data):
    from . import category_intake as capture
    from .governance_views import audit
    from .template_views import require_field_editable
    Checklist.objects.select_for_update().get(pk=checklist_id)
    c,flags=capture.access(request,checklist_id,edit=True)
    capture._same_source(c,data.get('expected_digest'))
    current=describe(c,flags)
    if data.get('expected_general_digest')!=current['digest']:
        raise ValidationError('General Info changed. Refresh the saved site information before applying your edits.')
    if set(data)-{'expected_digest','expected_general_digest','site_information','general_info'}:
        raise ValidationError('Change only the editable site information and approved General Info fields.')
    supplied=data.get('general_info',{});basics=data.get('site_information',{})
    if not isinstance(supplied,dict) or len(supplied)>300 or not isinstance(basics,dict) or set(basics)-set(BASICS):
        raise ValidationError('Provide approved General Info fields and known site information as objects.')
    fields={row['id']:row for row in current['fields'] if row['scope']=='general'}
    validated={}
    for ident,value in supplied.items():
        field=fields.get(ident)
        if not field or not field['editable']:raise ValidationError('Unknown or read-only General Info field: '+str(ident)[:80]+'.')
        if field['type']=='number' and type(value) in (int,float):value=str(value)
        validate_answer(field,value);require_field_editable(c,ident)
        validated[ident]=value
    for key,value in basics.items():
        if not isinstance(value,str) or len(value)>BASICS[key][1]:raise ValidationError('Provide valid text for '+BASICS[key][0]+'.')
    before_answers=deepcopy(c.answer_data or {});before_metadata=deepcopy(c.intake_metadata or {})
    answers=deepcopy(before_answers)
    if validated:answers.setdefault('custom',{}).update(validated)
    c.answer_data=answers
    saved_basic=deepcopy(before_metadata.get('site_information',{}))
    if not isinstance(saved_basic,dict):saved_basic={}
    saved_basic.update(basics)
    c.intake_metadata={**before_metadata,'site_information':saved_basic}
    provenance=deepcopy(before_metadata.get('general_information_sources',{}))
    if not isinstance(provenance,dict):provenance={}
    previous=before_answers.get('custom',{})
    for ident,value in validated.items():
        if ident in previous and previous[ident]==value and ident in provenance:continue
        row=fields[ident]
        prefilled=row['prefilled'] and row['value']==value
        provenance[ident]={'source':row['source'] if prefilled else 'engineer_entry',
            'note':row['source_note'] if prefilled else 'Explicitly recorded by the assigned Engineer.','by':request.user.pk}
    for key,value in basics.items():
        if key in before_metadata.get('site_information',{}) and before_metadata['site_information'][key]==value and 'site:'+key in provenance:continue
        provenance['site:'+key]={'source':'engineer_entry','note':'Explicitly recorded by the assigned Engineer.','by':request.user.pk}
    if provenance:c.intake_metadata['general_information_sources']=provenance
    prefills=materialize_missing(c)
    if c.answer_data!=before_answers or c.intake_metadata!=before_metadata:
        c.review_history=[*(c.review_history or []),{'action':'engineer_general_information_saved','by':request.user.pk,
            'time':timezone.now().isoformat(),'field_ids':list(validated),'site_keys':list(basics),'prefilled_field_ids':prefills}]
        c.save(update_fields=['answer_data','intake_metadata','review_history','updated_at'])
        WorkAssignment.objects.filter(checklist=c,status=WorkAssignment.Status.PENDING).update(status=WorkAssignment.Status.IN_PROGRESS,started_at=timezone.now())
        audit(request.user,'engineer_general_information_saved',c.project,checklist_id=c.pk,
            field_ids=list(validated),site_keys=list(basics),prefilled_field_ids=prefills)
    return capture.state(request,checklist_id)
