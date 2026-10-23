"""Frozen per-task reviewer routing; clarifications never change source evidence."""
import hashlib
import json
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from .access import role_for,can_access_project,is_super_admin
from .models import Checklist,Profile,WorkAssignment
from .revision_models import SubmissionRevision,RevisionDecision
from .review_route_models import ReviewRoute,ReviewRouteEvent

STAGES=('engineer','quality_engineer','team_lead','client')
LABELS={'engineer':'Engineer','quality_engineer':'Quality Engineer','team_lead':'Team Lead','client':'Client','closed':'Closed'}
ROLES={'engineer':Profile.Roles.ENGINEER,'quality_engineer':Profile.Roles.QUALITY_ENGINEER,'team_lead':Profile.Roles.TEAM_LEAD,'client':Profile.Roles.CLIENT}

def route_for(checklist):
    return ReviewRoute.objects.select_related('revision').filter(checklist_id=checklist.pk).first()

def token_for(route,checklist):
    data=[route.pk,route.layer_count,route.reviewers,route.stage,route.mode,route.revision_id,route.generation,checklist.updated_at.isoformat(),checklist.status]
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _actor_allowed(actor,checklist,route):
    return bool(not is_super_admin(actor) and route.stage in ROLES and role_for(actor)==ROLES[route.stage] and route.reviewers.get(route.stage)==actor.pk and can_access_project(actor,checklist.project_id))

def route_context(actor,checklist):
    route=route_for(checklist)
    if not route:return None
    index=STAGES.index(route.stage) if route.stage in STAGES else -1
    active=_actor_allowed(actor,checklist,route)
    can_review=active and route.stage!='engineer'
    previous=STAGES[index-1] if index>0 else None
    following=STAGES[index+1] if 0<=index<route.layer_count-1 else None
    qa_review_required=False
    qa_review_message=''
    if can_review and route.stage=='quality_engineer':
        from .category_intake import enabled as intake_enabled,require_qa_complete
        if intake_enabled(checklist):
            try:require_qa_complete(checklist)
            except ValidationError:
                qa_review_required=True
                qa_review_message='Review and complete the current QA evidence package before approving or responding to this clarification.'
    return {'layers':route.layer_count,'stage':route.stage,'label':LABELS[route.stage],'mode':route.mode,'token':token_for(route,checklist),'can_act':can_review,'can_approve':can_review and route.mode=='review' and not qa_review_required,'can_reject':can_review and route.mode=='review','can_clarify':can_review and route.mode=='clarification' and following is not None and not qa_review_required,'can_return':can_review and route.mode=='clarification' and previous is not None,'qa_review_required':qa_review_required,'qa_review_message':qa_review_message,'previous_label':LABELS.get(previous,''),'next_label':LABELS.get(following,''),'events':route.events.select_related('actor').order_by('sequence')}

def _event(actor,checklist,route,from_stage,action,reason=''):
    route.generation+=1
    route.save(update_fields=['stage','mode','revision','generation'])
    event=ReviewRouteEvent.objects.create(route=route,sequence=route.generation,revision=route.revision,revision_digest=route.revision.digest if route.revision else '',from_stage=from_stage,to_stage=route.stage,action=action,reason=reason,actor=actor)
    from .governance_views import audit
    audit(actor,'review_route_'+action,checklist.project,checklist_id=checklist.pk,route_id=route.pk,sequence=event.sequence,from_stage=from_stage,to_stage=route.stage,revision_id=route.revision_id,reason=reason)
    return event

@transaction.atomic
def configure_route(actor,checklist,policy):
    existing=route_for(checklist)
    layers=(checklist.intake_metadata or {}).get('project_review_layers')
    if existing:
        if layers!=existing.layer_count:raise ValidationError('The task creation policy does not match its frozen review route.')
        if existing.reviewers!={'engineer':checklist.user_id,'quality_engineer':policy.l2_reviewer_id,'team_lead':policy.l3_approver_id,**({'client':policy.customer_reviewer_id} if existing.layer_count==4 else {})} or policy.customer_required!=(existing.layer_count==4):raise ValidationError('This task has a frozen project review route; reviewers cannot be silently changed.')
        return existing
    # An existing task is never converted merely because project settings changed.
    if layers is None or checklist.submission_revisions.exists():return None
    if type(layers) is not int:raise ValidationError('The frozen task review layer count is invalid.')
    if layers not in {3,4} or policy.workflow_version!=2 or checklist.governance_mode!='independent':raise ValidationError('Project routing requires independent Engineer, Quality Engineer and Team Lead review.')
    if policy.customer_required!=(layers==4) or (layers==4 and not policy.customer_reviewer_id) or (layers==3 and policy.customer_reviewer_id):raise ValidationError('Use exactly the project three- or four-layer Client policy.')
    route=ReviewRoute.objects.create(checklist=checklist,layer_count=layers,reviewers={'engineer':checklist.user_id,'quality_engineer':policy.l2_reviewer_id,'team_lead':policy.l3_approver_id,**({'client':policy.customer_reviewer_id} if layers==4 else {})})
    _event(actor,checklist,route,'engineer','configure',policy.reason)
    return route


def _valid_reviewers(checklist,route):
    if len(set(route.reviewers.values()))!=route.layer_count:raise ValidationError('Every routed reviewer must be a distinct person.')
    for stage,pk in route.reviewers.items():
        actor=User.objects.filter(pk=pk).first()
        if not actor or role_for(actor)!=ROLES[stage] or not can_access_project(actor,checklist.project_id):raise ValidationError('An assigned routed reviewer is inactive, revoked or no longer has the required project role.')

def _check_digest(checklist,route):
    from .independent_workflow import content_snapshot,snapshot_digest
    if not route.revision or snapshot_digest(content_snapshot(checklist))!=route.revision.digest:raise ValidationError('Frozen inputs changed. Return one step for correction; source changes require Engineer resubmission.')

@transaction.atomic
def submit_route(actor,checklist):
    from .governance_views import lock_governance
    from .template_service import missing_required
    from .roadmap_service import require_qualified_template
    from .independent_workflow import content_snapshot,snapshot_digest,policy_for
    lock_governance(actor);actor=User.objects.get(pk=actor.pk)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    route=ReviewRoute.objects.select_for_update().get(checklist=checklist)
    if route.stage!='engineer' or not _actor_allowed(actor,checklist,route):raise PermissionDenied('Only the current assigned Engineer may submit this correction.')
    if checklist.status not in {Checklist.Status.DRAFT,Checklist.Status.REJECTED}:raise ValidationError('This task is not in Engineer preparation.')
    _valid_reviewers(checklist,route)
    from .category_intake import enabled as intake_enabled, validate_handoff
    if intake_enabled(checklist):
        validate_handoff(checklist);missing=[]
    else:
        require_qualified_template(checklist);missing=missing_required(checklist)
    if missing:raise ValidationError('Complete required fields: '+', '.join(missing))
    policy=policy_for(checklist)
    if not policy or policy.current_revision_id!=route.revision_id:raise ValidationError('The frozen review policy changed.')
    snapshot=content_snapshot(checklist);number=(checklist.submission_revisions.aggregate(value=Max('number'))['value'] or 0)+1
    revision=SubmissionRevision.objects.create(workflow_version=2,checklist=checklist,number=number,parent=route.revision,snapshot=snapshot,digest=snapshot_digest(snapshot),submitted_by=actor,l2_reviewer_id=route.reviewers['quality_engineer'],l3_approver_id=route.reviewers['team_lead'])
    RevisionDecision.objects.create(revision=revision,action='submit',level='L1',actor=actor)
    route.revision=revision;route.stage='quality_engineer';route.mode='review'
    policy.current_revision=revision;policy.save(update_fields=['current_revision'])
    checklist.status=Checklist.Status.SUBMITTED;checklist.section_approvals={};checklist.quality_approval={};checklist.client_approval={};checklist.client_review_required=(route.layer_count==4);checklist.client_review_completed_at=None
    checklist.review_history=[*(checklist.review_history or []),{'action':'route_revision_submitted','revision_id':revision.pk,'by':actor.pk,'time':timezone.now().isoformat()}]
    checklist.save(update_fields=['status','section_approvals','quality_approval','client_approval','client_review_required','client_review_completed_at','review_history','updated_at'])
    _event(actor,checklist,route,'engineer','submit')
    WorkAssignment.objects.filter(checklist=checklist).update(status=WorkAssignment.Status.SUBMITTED,submitted_at=timezone.now(),completed_at=None)
    return revision

@transaction.atomic
def act_on_route(actor,checklist,action,reason='',expected_token=None):
    from .governance_views import lock_governance
    from .roadmap_service import require_no_blocking_findings
    lock_governance(actor);actor=User.objects.get(pk=actor.pk)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    route=ReviewRoute.objects.select_for_update().select_related('revision').get(checklist=checklist)
    if not _actor_allowed(actor,checklist,route) or route.stage=='engineer':raise PermissionDenied('Only the currently assigned named reviewer may act at this stage.')
    if not expected_token or expected_token!=token_for(route,checklist):raise ValidationError('The route changed. Reload before recording a decision.')
    if action not in {'approve','reject','clarify','return'}:raise ValidationError('Choose a supported route action.')
    if not isinstance(reason,str) or len(reason)>4000 or action in {'reject','clarify','return'} and not reason.strip():raise ValidationError('This action requires a reason of at most 4000 characters.')
    if not route.revision:raise ValidationError('Submit a frozen revision before review.')
    before=route.stage;index=STAGES.index(before)
    if route.mode=='review' and action not in {'approve','reject'} or route.mode=='clarification' and action not in {'clarify','return'}:raise ValidationError('Use the action available at the current review or clarification stage.')
    if action in {'approve','clarify'}:
        _check_digest(checklist,route);require_no_blocking_findings(checklist)
        from .category_intake import enabled as intake_enabled, record_qa_approval
        if intake_enabled(checklist) and before=='quality_engineer':record_qa_approval(checklist,actor)
    if action in {'reject','return'}:
        route.stage=STAGES[index-1];route.mode='clarification'
        from .category_intake import enabled as intake_enabled,current_revision
        if intake_enabled(checklist) and route.stage=='quality_engineer':
            from .survey_processing_models import SurveyProcessingEvent
            SurveyProcessingEvent.objects.create(revision=current_revision(checklist),actor=actor,action='qa_reopen',reason=reason.strip())
    else:
        route.stage=STAGES[index+1] if index<route.layer_count-1 else 'closed';route.mode='review'
    if action=='approve':
        signature={'quality_engineer':('validate','L2'),'team_lead':('approve','L3'),'client':('customer_approve','C1')}[before]
        # Historical signatures are retained; repeated review is recorded in route events.
        if not route.revision.decisions.filter(action=signature[0]).exists():RevisionDecision.objects.create(revision=route.revision,action=signature[0],level=signature[1],actor=actor,reason=reason.strip())
    if route.stage=='engineer':
        checklist.status=Checklist.Status.REJECTED;checklist.section_approvals={};checklist.quality_approval={}
    elif route.stage in {'client','closed'}:
        checklist.status=Checklist.Status.FINAL
        checklist.section_approvals={section['id']:{'by':route.reviewers['team_lead'],'time':timezone.now().isoformat(),'revision_id':route.revision_id} for section in route.revision.snapshot['schema']['sections']}
    else:checklist.status=Checklist.Status.SUBMITTED if route.stage=='quality_engineer' and route.mode=='review' else Checklist.Status.REVIEW
    checklist.client_review_required=(route.layer_count==4)
    if route.stage=='closed' and route.layer_count==4:checklist.client_review_completed_at=timezone.now()
    elif route.stage!='closed':checklist.client_review_completed_at=None
    if before=='client':checklist.client_approval={'decision':'approved' if action=='approve' else 'rejected','authenticated_client':True,'approver_name':actor.get_full_name() or 'Assigned Client','approver_email':actor.email,'time':timezone.now().isoformat(),'reference':reason.strip()}
    checklist.review_history=[*(checklist.review_history or []),{'action':'route_'+action,'from':before,'to':route.stage,'reason':reason.strip(),'by':actor.pk,'revision_id':route.revision_id,'time':timezone.now().isoformat()}]
    checklist.save(update_fields=['status','section_approvals','quality_approval','client_review_required','client_review_completed_at','client_approval','review_history','updated_at'])
    event=_event(actor,checklist,route,before,action,reason.strip())
    status=WorkAssignment.Status.COMPLETED if route.stage=='closed' else WorkAssignment.Status.CLIENT_REVIEW if route.stage=='client' else WorkAssignment.Status.IN_PROGRESS if route.stage=='engineer' else WorkAssignment.Status.SUBMITTED
    WorkAssignment.objects.filter(checklist=checklist).update(status=status,completed_at=timezone.now() if route.stage=='closed' else None)
    return event
