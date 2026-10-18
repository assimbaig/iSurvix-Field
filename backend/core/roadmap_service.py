"""Pilot qualification and finding gates, independent from administrative rights."""
import hashlib
import json
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from .models import Checklist,Profile,WorkflowTemplateQualification,InspectionFinding,FindingEvent
from .access import role_for,can_access_project,is_super_admin


def definition_digest(definition):
    return hashlib.sha256(json.dumps(definition,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def current_qualification(checklist):
    return WorkflowTemplateQualification.objects.filter(project_id=checklist.project_id,template_id=checklist.checklist_template_id,workflow_type=checklist.workflow_type,definition_digest=definition_digest(checklist.schema_snapshot)).order_by('-pk').first()


def require_qualified_template(checklist):
    if checklist.governance_mode!=Checklist.GovernanceMode.INDEPENDENT:return
    if not current_qualification(checklist):
        raise ValidationError('A project Team Lead must record technical applicability, criteria and method for this exact template revision before submission.')
    if checklist.workflow_type!=Checklist.WorkflowType.TELECOM_SURVEY and not checklist.asset_reference.strip():
        raise ValidationError('Identify the inspected asset or work location before submission.')
    if not all(str(checklist.coordinate_reference.get(key,'')).strip() for key in ['source','crs']):
        raise ValidationError('Record the coordinate source and datum/CRS before submission; do not guess either value.')


def require_no_blocking_findings(checklist):
    if checklist.inspection_findings.exclude(status='closed').filter(blocking=True).exists() or checklist.inspection_findings.exclude(status='closed').filter(severity='critical').exists():
        raise ValidationError('Open blocking or critical findings prevent release. Record remedy and independent retest first.')


@transaction.atomic
def qualify_template(actor,project,workflow_type,criteria_reference,inspection_method,reason):
    from .governance_views import lock_governance,audit
    lock_governance(actor)
    if is_super_admin(actor) or role_for(actor) not in {Profile.Roles.TEAM_LEAD,Profile.Roles.PROJECT_MANAGER} or not can_access_project(actor,project):
        raise PermissionDenied('Technical qualification requires an active project Team Lead or historical Project Manager; administrative privilege is insufficient.')
    expected='construction' if workflow_type==Checklist.WorkflowType.CONSTRUCTION_INSPECTION else 'telecom'
    if workflow_type not in Checklist.WorkflowType.values or project.industry!=expected:
        raise ValidationError('Choose an applicable workflow for the project industry.')
    template=project.checklist_template
    if not template or not template.published:raise ValidationError('Select a published project template first.')
    for value in [criteria_reference,inspection_method,reason]:
        if not isinstance(value,str) or not value.strip() or len(value)>4000:raise ValidationError('Record criteria, inspection method and applicability reason (up to 4000 characters each).')
    record=WorkflowTemplateQualification.objects.create(project=project,template=template,workflow_type=workflow_type,definition_digest=definition_digest(template.definition),criteria_reference=criteria_reference,inspection_method=inspection_method,reason=reason,reviewed_by=actor)
    audit(actor,'template_technically_qualified',project,qualification_id=record.pk,workflow_type=workflow_type,definition_digest=record.definition_digest)
    return record


def validate_photos(checklist,photo_ids):
    if not isinstance(photo_ids,list) or len(photo_ids)>400 or any(type(pid)!=int for pid in photo_ids) or len(photo_ids)!=len(set(photo_ids)):
        raise ValidationError('Choose distinct photos from this activity, up to400.')
    if checklist.photo_evidence.filter(pk__in=photo_ids).count()!=len(photo_ids):raise ValidationError('A source photo belongs to another activity.')


@transaction.atomic
def record_finding(actor,checklist,description,severity,blocking=True,photo_ids=None,owner=None,due_date=None):
    from types import SimpleNamespace
    from .governance_views import lock_governance,audit
    from .template_views import survey_access
    lock_governance(actor)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if checklist.governance_mode!=Checklist.GovernanceMode.INDEPENDENT:raise ValidationError('The finding register requires an independently governed inspection activity.')
    survey_access(SimpleNamespace(user=actor),checklist.pk,edit=True)
    if is_super_admin(actor) or role_for(actor)!=Profile.Roles.ENGINEER or checklist.user_id!=actor.pk:raise PermissionDenied('The assigned Engineer records inspection findings during preparation or correction.')
    if not description.strip() or len(description)>4000 or severity not in {'low','medium','high','critical'}:raise ValidationError('Record a finding and valid severity.')
    photo_ids=photo_ids or []
    validate_photos(checklist,photo_ids)
    if owner and not can_access_project(owner,checklist.project_id):raise ValidationError('The action owner must belong to this project.')
    finding=InspectionFinding.objects.create(checklist=checklist,description=description,severity=severity,blocking=bool(blocking) or severity=='critical',photo_ids=photo_ids,owner=owner or actor,due_date=due_date,created_by=actor,asset_reference=checklist.asset_reference)
    FindingEvent.objects.create(finding=finding,action='opened',reason=description,photo_ids=photo_ids,actor=actor)
    audit(actor,'inspection_finding_opened',checklist.project,finding_id=finding.pk,checklist_id=checklist.pk)
    return finding


@transaction.atomic
def finding_action(actor,finding,action,reason,photo_ids=None):
    from types import SimpleNamespace
    from .governance_views import lock_governance,audit
    from .template_views import survey_access
    lock_governance(actor)
    finding=InspectionFinding.objects.select_for_update().select_related('checklist').get(pk=finding.pk)
    checklist=finding.checklist
    survey_access(SimpleNamespace(user=actor),checklist.pk)
    from .independent_workflow import is_frozen
    if is_frozen(checklist):raise ValidationError('Return the submitted revision before remedy or retest changes; its source snapshot remains frozen.')
    if not reason.strip() or len(reason)>4000:raise ValidationError('Record the remedy or retest evidence and reason.')
    if checklist.status==Checklist.Status.FINAL or finding.status=='closed':raise ValidationError('Final activities and closed findings retain their recorded history.')
    photo_ids=photo_ids or []
    validate_photos(checklist,photo_ids)
    if action=='remedy':
        if is_super_admin(actor) or role_for(actor)!=Profile.Roles.ENGINEER or actor.pk not in {checklist.user_id,finding.owner_id}:raise PermissionDenied('Only the assigned Engineer or Engineer action owner records remedy.')
        survey_access(SimpleNamespace(user=actor),checklist.pk,edit=True)
        finding.status='remedied'
    elif action=='retest':
        policy=getattr(checklist,'review_policy',None)
        assigned=bool(policy and actor.pk in {policy.l2_reviewer_id,policy.l3_approver_id})
        if is_super_admin(actor) or not assigned or role_for(actor) not in {Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.PROJECT_MANAGER}:raise PermissionDenied('Independent retest requires the explicitly assigned technical reviewer.')
        if finding.status!='remedied' or actor.pk==finding.created_by_id or finding.events.filter(action='remedy',actor=actor).exists():raise ValidationError('Record remedy first; the retest actor must be independent of the finding author and remediator.')
        finding.status='closed'
    else:raise ValidationError('Choose remedy or independently verified retest.')
    FindingEvent.objects.create(finding=finding,action=action,reason=reason,photo_ids=photo_ids,actor=actor)
    finding.save(update_fields=['status'])
    audit(actor,'inspection_finding_'+action,checklist.project,finding_id=finding.pk,checklist_id=checklist.pk)
    return finding
