"""Mandatory, attributed Quality Control before legacy Team Lead approval."""
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Checklist,Profile
from .access import role_for,can_access_project


def require_quality_reviewer(project_id,reviewer,engineer_id):
    reviewer=User.objects.get(pk=reviewer.pk) if reviewer else None
    if not reviewer or reviewer.pk==engineer_id or role_for(reviewer)!=Profile.Roles.QUALITY_ENGINEER or not can_access_project(reviewer,project_id):
        raise ValidationError('Assign an active project Quality Engineer before submission.')
    return reviewer


def quality_digest(checklist):
    from .independent_workflow import content_snapshot,snapshot_digest
    return snapshot_digest(content_snapshot(checklist))


def quality_is_current(checklist):
    approval=checklist.quality_approval or {}
    return bool(approval.get('decision')=='approved' and approval.get('reviewer_id')==checklist.quality_reviewer_id and approval.get('digest')==quality_digest(checklist))


@transaction.atomic
def review_quality(actor,checklist,decision,reason='',expected_updated_at=''):
    from .governance_views import lock_governance,audit
    from .workflow_service import sync_assignment
    lock_governance(actor)
    actor=User.objects.get(pk=actor.pk)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if checklist.governance_mode=='independent':
        raise ValidationError('Use the revision-bound Quality Control decision for independent workflows.')
    if role_for(actor)!=Profile.Roles.QUALITY_ENGINEER or actor.pk!=checklist.quality_reviewer_id or not can_access_project(actor,checklist.project_id):
        raise PermissionDenied('Only the assigned project Quality Engineer may record Quality Control.')
    if not expected_updated_at or expected_updated_at!=checklist.updated_at.isoformat():
        raise ValidationError('The submitted checklist changed. Reload before recording Quality Control.')
    if checklist.status not in {Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL} or quality_is_current(checklist):
        raise ValidationError('This checklist is not awaiting Quality Control.')
    if decision not in {'approve','reject'} or not isinstance(reason,str) or len(reason)>4000 or decision=='reject' and not reason.strip():
        raise ValidationError('Choose approve or reject; rejection requires a reason of at most 4000 characters.')
    record={'decision':'approved' if decision=='approve' else 'rejected','reviewer_id':actor.pk,'name':actor.username,'reason':reason.strip(),'time':timezone.now().isoformat(),'digest':quality_digest(checklist)}
    checklist.quality_approval=record
    if decision=='reject':
        checklist.status=Checklist.Status.REJECTED
        checklist.section_approvals={}
    else:
        checklist.status=Checklist.Status.REVIEW
    checklist.review_history=[*(checklist.review_history or []),{'action':'quality_'+decision,**record}]
    checklist.save(update_fields=['quality_approval','status','section_approvals','review_history','updated_at'])
    sync_assignment(checklist)
    audit(actor,'quality_'+decision,checklist.project,checklist_id=checklist.pk,reason=reason.strip())
    return record

@transaction.atomic
def assign_quality_reviewer(actor,checklist,reviewer,reason,expected_updated_at):
    from .governance_views import lock_governance,audit
    lock_governance(actor)
    actor=User.objects.get(pk=actor.pk)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if role_for(actor) not in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD} or not can_access_project(actor,checklist.project_id):
        raise PermissionDenied('Only the scoped Project Admin or Team Lead may assign Quality Control.')
    if checklist.governance_mode=='independent' or checklist.status==Checklist.Status.FINAL:
        raise ValidationError('Frozen or independently governed reviewers require their explicit policy controls.')
    if expected_updated_at!=checklist.updated_at.isoformat():
        raise ValidationError('This checklist changed; reload before assigning Quality Control.')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>4000:
        raise ValidationError('Record the Quality Engineer assignment reason.')
    reviewer=require_quality_reviewer(checklist.project_id,reviewer,checklist.user_id)
    checklist.quality_reviewer=reviewer
    checklist.quality_approval={}
    checklist.review_history=[*(checklist.review_history or []),{'action':'quality_assigned','by':actor.pk,'reviewer_id':reviewer.pk,'reason':reason.strip(),'time':timezone.now().isoformat()}]
    checklist.save(update_fields=['quality_reviewer','quality_approval','review_history','updated_at'])
    audit(actor,'quality_assigned',checklist.project,checklist_id=checklist.pk,reviewer_id=reviewer.pk,reason=reason.strip())
    return checklist
