"""Authoritative internal-review/client-review/activity closure transitions.

Call mutation helpers inside the caller's transaction with checklist locked.
Historical nullable routing markers are deliberately not inferred or backfilled.
"""
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from .models import Checklist,WorkAssignment,Profile,ProjectInvitation
from django.contrib.auth.models import User


def configured_client_review(project_id):
    # Assignment is configuration, even when an account is temporarily disabled/locked.
    from .access import users_for_project
    if users_for_project(project_id,{Profile.Roles.CLIENT},include_inactive=True).exists():
        return True
    from .governance_views import issue_guard
    pending=ProjectInvitation.objects.filter(project_id=project_id,role=Profile.Roles.CLIENT,accepted_at__isnull=True,revoked_at__isnull=True,expires_at__gt=timezone.now()).select_related('created_by','created_by__profile','project')
    for invitation in pending:
        issuer=invitation.created_by
        if not issuer:
            continue
        try:
            issue_guard(issuer,invitation.project,invitation.role)
        except PermissionDenied:
            continue
        return True
    return False


def closed_activity(checklist):
    if checklist.client_review_completed_at or checklist.client_review_required is False:
        return True
    return WorkAssignment.objects.filter(checklist_id=checklist.pk,status=WorkAssignment.Status.COMPLETED).exists()


def can_client_decide(checklist):
    return checklist.status==Checklist.Status.FINAL and not closed_activity(checklist)


def workflow_stage(checklist):
    if getattr(checklist,'governance_mode','legacy')=='independent':
        from .independent_workflow import policy_for,revision_state
        policy=policy_for(checklist)
        if policy and policy.current_revision_id:
            state=revision_state(policy.current_revision)
            if state=='submitted':
                return 'quality_engineer' if policy.current_revision.workflow_version==2 else 'team_lead'
            if state=='validated':
                return 'team_lead' if policy.current_revision.workflow_version==2 else 'project_manager'
            if state in {'returned','customer_rejected'}:
                return 'engineer'
    if checklist.status==Checklist.Status.FINAL:
        if closed_activity(checklist):
            return 'closed'
        return 'client' if checklist.client_review_required is True else 'team_lead'
    if checklist.status in {Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL}:
        from .quality_workflow import quality_is_current
        return 'team_lead' if quality_is_current(checklist) else 'quality_engineer'
    return 'engineer'


def workflow_label(checklist):
    stage=workflow_stage(checklist)
    if stage=='closed':
        return 'Activity closed - no client review configured' if checklist.client_review_required is False else 'Activity closed'
    if stage=='quality_engineer':
        return 'Awaiting assigned Quality Engineer review'
    if stage=='project_manager':
        return 'Awaiting assigned Project Manager L3 approval'
    if stage=='client':
        return 'Awaiting client approval - client rejected' if (checklist.client_approval or {}).get('decision')=='rejected' else 'Awaiting client approval'
    if checklist.status==Checklist.Status.FINAL:
        return 'Internally approved - historical routing not recorded'
    if checklist.status==Checklist.Status.PARTIAL:
        return 'Partially approved - remaining sections open'
    if stage=='team_lead':
        return 'Awaiting Team Lead review'
    return 'Engineer corrections required' if checklist.status==Checklist.Status.REJECTED else 'Engineer preparation'


def sync_assignment(checklist):
    work=WorkAssignment.objects.filter(checklist=checklist)
    now=timezone.now()
    if checklist.status==Checklist.Status.FINAL:
        # Preserve historical completion. Do not manufacture a routing decision.
        if checklist.client_review_required is None:
            return
        if checklist.client_review_required is False or checklist.client_review_completed_at:
            work.exclude(status=WorkAssignment.Status.COMPLETED).update(status=WorkAssignment.Status.COMPLETED,completed_at=checklist.client_review_completed_at or now)
        else:
            work.update(status=WorkAssignment.Status.CLIENT_REVIEW,completed_at=None)
    else:
        status=WorkAssignment.Status.SUBMITTED if checklist.status in {Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL} else WorkAssignment.Status.IN_PROGRESS
        work.exclude(status=WorkAssignment.Status.COMPLETED).update(status=status,completed_at=None)
    # Clear a previously cached reverse relation so UI/signature checks see the update.
    checklist._state.fields_cache.pop('work_assignment',None)


def internal_review_completed(checklist,actor):
    if checklist.status!=Checklist.Status.FINAL:
        sync_assignment(checklist)
        return
    if checklist.client_review_required is None:
        checklist.client_review_required=configured_client_review(checklist.project_id)
        checklist.client_review_routed_at=timezone.now()
        checklist.save(update_fields=['client_review_required','client_review_routed_at','updated_at'])
        from .governance_views import audit
        audit(actor,'client_review_routed',checklist.project,checklist_id=checklist.pk,client_review_required=checklist.client_review_required)
    sync_assignment(checklist)


def apply_client_decision(checklist,actor,authenticated_client):
    if not can_client_decide(checklist):
        raise ValidationError('This activity is already closed or is not awaiting a client decision.')
    if checklist.client_review_required is True and authenticated_client and checklist.client_approval.get('decision')=='approved':
        checklist.client_review_completed_at=timezone.now()
    # Administrator-recorded external correspondence cannot close a required client gate.
