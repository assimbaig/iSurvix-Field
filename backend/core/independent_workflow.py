"""Versioned immutable review: new Engineer -> Quality Engineer -> Team Lead."""
import hashlib
import json
from copy import deepcopy
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone
from .access import can_access_project,role_for,is_super_admin,project_role_guard
from .models import Checklist,Profile,WorkAssignment
from .revision_models import ChecklistReviewPolicy,SubmissionRevision,RevisionDecision


def revision_state(revision):
    actions=set(revision.decisions.values_list('action',flat=True))
    return 'customer_rejected' if 'customer_reject' in actions else 'returned' if 'return' in actions else 'approved' if 'approve' in actions else 'validated' if 'validate' in actions else 'submitted'


def policy_for(checklist):
    return ChecklistReviewPolicy.objects.select_related('current_revision').filter(checklist=checklist).first()


def is_independent(checklist):
    return getattr(checklist,'governance_mode','legacy')=='independent'


def is_frozen(checklist):
    from .review_route_service import route_for
    route=route_for(checklist) if is_independent(checklist) else None
    if route:return route.stage!='engineer'
    policy=policy_for(checklist) if is_independent(checklist) else None
    return bool(policy and policy.current_revision_id and revision_state(policy.current_revision) in {'submitted','validated','approved'})


def assigned_site_access(actor,checklist):
    if is_super_admin(actor):
        return False
    if not can_access_project(actor,checklist.project_id):
        return False
    role=role_for(actor)
    if is_super_admin(actor) or role==Profile.Roles.ADMIN:
        return True
    if role==Profile.Roles.CLIENT:
        policy=policy_for(checklist)
        from .review_route_service import route_for
        route=route_for(checklist)
        if route:
            shared=route.revision_id and route.events.filter(revision_id=route.revision_id,from_stage='team_lead',to_stage='client').exists()
            return route.stage!='engineer' and shared and route.reviewers.get('client')==actor.pk
        return checklist.status==Checklist.Status.FINAL and bool(policy and policy.customer_reviewer_id==actor.pk)
    if role==Profile.Roles.ENGINEER:
        return checklist.user_id==actor.pk
    policy=policy_for(checklist)
    return bool(policy and (policy.workflow_version==2 and (role==Profile.Roles.QUALITY_ENGINEER and policy.l2_reviewer_id==actor.pk or role==Profile.Roles.TEAM_LEAD and policy.l3_approver_id==actor.pk) or policy.workflow_version==1 and (role==Profile.Roles.TEAM_LEAD and policy.l2_reviewer_id==actor.pk or role==Profile.Roles.PROJECT_MANAGER and policy.l3_approver_id==actor.pk)))


def content_snapshot(checklist):
    # Model-managed originals are never overwritten; retain authenticated source paths
    # and their exact upload hashes, plus frozen confirmed many-to-many item links.
    photos=list(checklist.photo_evidence.order_by('pk').values('id','filename','sha256','original','metadata','uploaded_by_id','created_at'))
    from .category_intake import enabled as intake_enabled,current_revision
    intake_revision=current_revision(checklist) if intake_enabled(checklist) else None
    if intake_revision:
        captured={p['id']:p for p in intake_revision.snapshot['photos']}
        photos=[{**photo,'group':captured[photo['id']].get('group','')} for photo in photos if photo['id'] in captured]
    placements=[]
    for photo in checklist.photo_evidence.order_by('pk'):
        placements.extend(photo.placements.filter(status__in=['manual','confirmed']).order_by('pk').values('photo_id','field_id','section_id','status','reviewed_by_id','reviewed_at'))
    policy=policy_for(checklist)
    review_policy={'l2_reviewer_id':policy.l2_reviewer_id,'l3_approver_id':policy.l3_approver_id,'customer_reviewer_id':policy.customer_reviewer_id,'customer_required':policy.customer_required,'applicability_reason':policy.applicability_reason} if policy else None
    if policy and policy.workflow_version==2:
        review_policy['workflow_version']=2
    from .roadmap_service import current_qualification
    from .roadmap_models import FindingEvent
    qualification=current_qualification(checklist)
    qualification_data={key:getattr(qualification,key) for key in ['id','definition_digest','criteria_reference','inspection_method','reviewed_by_id','reviewed_at','reason']} if qualification else None
    findings=list(checklist.inspection_findings.order_by('pk').values())
    finding_events=list(FindingEvent.objects.filter(finding__checklist=checklist).order_by('pk').values())
    coordinates=WorkAssignment.objects.filter(checklist=checklist).values('latitude','longitude').first()
    project=checklist.project
    project_context={'id':project.pk,'name':project.name,'company_id':project.company_id,'industry':project.industry,'industry_name':project.get_industry_display()}
    from .review_route_service import route_for
    from .models import IndustryCatalog,GovernanceAudit
    route=route_for(checklist)
    catalog=IndustryCatalog.objects.filter(code=project.industry).first()
    baseline=(policy.current_revision.snapshot.get('project_context') or {}) if policy and policy.current_revision_id else {}
    if route and catalog:
        project_context['industry_catalog_id']=catalog.pk
    same_identity=bool(catalog and baseline and (
        baseline.get('industry_catalog_id')==catalog.pk or
        baseline.get('industry')==project.industry or
        GovernanceAudit.objects.filter(action='industry_updated',details__industry_id=catalog.pk,
            details__previous__code=baseline.get('industry')).exists()))
    if same_identity:
        # Catalog code/name are administrative labels. Keep their frozen display
        # representation while validating all actual engineering inputs afresh.
        project_context['industry']=baseline.get('industry',project_context['industry'])
        project_context['industry_name']=baseline.get('industry_name',project_context['industry_name'])
    if project.client_organization_id:
        project_context['client_organization']={'id':project.client_organization_id,'name':project.client_organization.name,'company_id':project.client_organization.company_id,'industry_id':project.client_organization.industry_id}
    data={'project_context':project_context,'qualification':qualification_data,'findings':findings,'finding_events':finding_events,'assigned_coordinates':coordinates,'engineer_id':checklist.user_id,'review_policy':review_policy,'site_id':checklist.site_id,'project_id':checklist.project_id,'template_id':checklist.checklist_template_id,
        'schema':checklist.schema_snapshot,'branding':checklist.branding_snapshot,'answers':checklist.answer_data,
        'remarks':checklist.remark_data,'field_images':checklist.image_data,'photos':photos,'placements':placements,
        'workflow_type':getattr(checklist,'workflow_type',''),'asset_reference':getattr(checklist,'asset_reference',''),
        'coordinate_reference':getattr(checklist,'coordinate_reference',{})}
    from .review_route_service import route_for
    route=route_for(checklist)
    if route:
        frozen_route={'version':1,'layers':route.layer_count,'reviewers':route.reviewers}
        data['review_route_policy']=frozen_route
    # Add provenance only for activities processed by the versioned pipeline;
    # legacy immutable snapshots retain their original representation.
    evidence=list(checklist.evidence_analyses.filter(photo__isnull=False).order_by('pk').values('id','photo_id','photo_sha256','schema_digest','rules_version','model_version','tool_version','prompt_version','payload_digest'))
    if evidence and not intake_enabled(checklist):
        data['evidence_analysis']=evidence
    return json.loads(json.dumps(data,cls=DjangoJSONEncoder,sort_keys=True))


def snapshot_digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def _fresh_actor(actor):
    return User.objects.get(pk=actor.pk)


def _roles_valid(checklist,l2,l3,version=2):
    engineer=User.objects.get(pk=checklist.user_id)
    if len({engineer.pk,l2.pk,l3.pk})!=3:
        raise ValidationError('Submission, validation and approval require three different people.')
    expected=((engineer,Profile.Roles.ENGINEER),(l2,Profile.Roles.QUALITY_ENGINEER if version==2 else Profile.Roles.TEAM_LEAD),(l3,Profile.Roles.TEAM_LEAD if version==2 else Profile.Roles.PROJECT_MANAGER))
    for person,role in expected:
        permitted={Profile.Roles.ADMIN,Profile.Roles.PROJECT_MANAGER} if version==1 and person.pk==l3.pk else {role}
        if role_for(person) not in permitted or not can_access_project(person,checklist.project_id):
            raise ValidationError('Each assigned person must have the required active project role.')


@transaction.atomic
def configure_policy(actor,checklist,l2_reviewer,l3_approver,reason,customer_reviewer=None,customer_required=None,expected_updated_at=None,enable_route=False):
    from .governance_views import lock_governance,audit
    lock_governance(actor)
    actor=_fresh_actor(actor)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if expected_updated_at is not None and expected_updated_at!=checklist.updated_at.isoformat():
        raise ValidationError('The checklist changed. Reload before assigning review policy.')
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot assign engineering reviewers.')
    project_role_guard(actor,checklist.project_id,{Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD})
    policy=policy_for(checklist)
    creating_lead=(role_for(actor)==Profile.Roles.TEAM_LEAD and checklist.status==Checklist.Status.DRAFT and checklist.intake_metadata.get('created_by')==actor.pk and not policy and not checklist.submission_revisions.exists())
    if not (is_super_admin(actor) or role_for(actor)==Profile.Roles.ADMIN or creating_lead):
        raise PermissionDenied('Only a scoped administrator or the creating Team Lead may configure initial reviewers.')
    if checklist.status not in {Checklist.Status.DRAFT,Checklist.Status.REJECTED}:
        raise ValidationError('Configure independent reviewers only on a draft or returned correction.')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>4000:
        raise ValidationError('Record the reason for the explicit review assignments.')
    policy=policy_for(checklist)
    if policy and policy.current_revision_id and not (policy.workflow_version==1 and revision_state(policy.current_revision) in {'returned','customer_rejected'}):
        raise ValidationError('A frozen revision cannot have its reviewers reassigned.')
    l2=_fresh_actor(l2_reviewer)
    l3=_fresh_actor(l3_approver)
    _roles_valid(checklist,l2,l3)
    if customer_required is None:
        from .workflow_service import configured_client_review
        customer_required=configured_client_review(checklist.project_id)
    if type(customer_required) is not bool:
        raise ValidationError('Record whether customer release is required.')
    customer=_fresh_actor(customer_reviewer) if customer_reviewer else None
    if customer_required and (not customer or role_for(customer)!=Profile.Roles.CLIENT or not can_access_project(customer,checklist.project_id)):
        raise ValidationError('Assign an active project Client when customer release is required.')
    if customer and not customer_required:
        raise ValidationError('Do not assign a customer reviewer to a not-required release policy.')
    if customer and customer.pk in {checklist.user_id,l2.pk,l3.pk}:
        raise ValidationError('Customer release must use a separate Client account.')
    policy,_=ChecklistReviewPolicy.objects.update_or_create(checklist=checklist,defaults={'workflow_version':2,'l2_reviewer':l2,'l3_approver':l3,'configured_by':actor,'reason':reason.strip(),'customer_reviewer':customer,'customer_required':customer_required,'applicability_reason':reason.strip()})
    checklist.governance_mode='independent'
    checklist.quality_reviewer=l2
    checklist.save(update_fields=['governance_mode','quality_reviewer','updated_at'])
    from .review_route_service import configure_route,route_for
    frozen_layers=(checklist.intake_metadata or {}).get('project_review_layers')
    if enable_route and (type(frozen_layers) is not int or frozen_layers not in (3,4)):
        raise ValidationError('Only a new task created under an explicit project review policy can enable routed review.')
    if frozen_layers in (3,4) and type(frozen_layers) is int or route_for(checklist):configure_route(actor,checklist,policy)
    audit(actor,'independent_review_configured',checklist.project,checklist_id=checklist.pk,l2_reviewer_id=l2.pk,l3_approver_id=l3.pk,reason=reason.strip())
    return policy


@transaction.atomic
def submit_revision(actor,checklist):
    from .review_route_service import route_for,submit_route
    if route_for(checklist):return submit_route(actor,checklist)
    from .governance_views import lock_governance,audit
    from .template_service import missing_required
    from .roadmap_service import require_qualified_template
    lock_governance(actor)
    actor=_fresh_actor(actor)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if not is_independent(checklist) or role_for(actor)!=Profile.Roles.ENGINEER or actor.pk!=checklist.user_id or not can_access_project(actor,checklist.project_id):
        raise PermissionDenied('Only the assigned Engineer may submit this independent revision.')
    if checklist.status not in {Checklist.Status.DRAFT,Checklist.Status.REJECTED}:
        raise ValidationError('Return the current revision before creating a correction.')
    policy=policy_for(checklist)
    if not policy or policy.workflow_version!=2:
        raise ValidationError('Assign a Quality Engineer and Team Lead under the current Quality Control workflow before a new submission.')
    if policy.current_revision_id and revision_state(policy.current_revision) not in {'returned','customer_rejected'}:
        raise ValidationError('The current frozen revision has not been returned.')
    _roles_valid(checklist,_fresh_actor(policy.l2_reviewer),_fresh_actor(policy.l3_approver))
    from .category_intake import enabled as intake_enabled, validate_handoff
    if intake_enabled(checklist):
        validate_handoff(checklist);missing=[]
    else:
        require_qualified_template(checklist);missing=missing_required(checklist)
    if missing:
        raise ValidationError('Complete required fields: '+', '.join(missing))
    snapshot=content_snapshot(checklist)
    number=(SubmissionRevision.objects.filter(checklist=checklist).aggregate(value=Max('number'))['value'] or 0)+1
    revision=SubmissionRevision.objects.create(workflow_version=2,checklist=checklist,number=number,parent=policy.current_revision,snapshot=snapshot,digest=snapshot_digest(snapshot),submitted_by=actor,l2_reviewer=policy.l2_reviewer,l3_approver=policy.l3_approver)
    RevisionDecision.objects.create(revision=revision,action='submit',level='L1',actor=actor)
    policy.current_revision=revision
    policy.save(update_fields=['current_revision'])
    checklist.status=Checklist.Status.SUBMITTED
    checklist.section_approvals={}
    checklist.client_approval={}
    checklist.client_review_completed_at=None
    checklist.review_history=[*(checklist.review_history or []),{'action':'revision_submitted','revision_id':revision.pk,'number':number,'digest':revision.digest,'by':actor.pk,'name':actor.username,'time':timezone.now().isoformat()}]
    checklist.save(update_fields=['status','section_approvals','review_history','client_approval','client_review_completed_at','updated_at'])
    WorkAssignment.objects.filter(checklist=checklist).exclude(status=WorkAssignment.Status.COMPLETED).update(status=WorkAssignment.Status.SUBMITTED,submitted_at=timezone.now())
    audit(actor,'revision_submitted',checklist.project,checklist_id=checklist.pk,revision_id=revision.pk,number=number,digest=revision.digest)
    return revision


@transaction.atomic
def review_revision(actor,checklist,revision_id,action,reason=''):
    from .review_route_service import route_for
    if route_for(checklist):raise ValidationError('Use the current token-bound review route action, not the historical revision endpoint.')
    from .governance_views import lock_governance,audit
    from .roadmap_service import require_no_blocking_findings
    lock_governance(actor)
    actor=_fresh_actor(actor)
    checklist=Checklist.objects.select_for_update().get(pk=checklist.pk)
    if not is_independent(checklist) or not assigned_site_access(actor,checklist):
        raise PermissionDenied('This independent Site is outside your explicit assignment.')
    policy=policy_for(checklist)
    revision=SubmissionRevision.objects.filter(pk=revision_id,checklist=checklist).first()
    if not policy or not revision or policy.current_revision_id!=revision.pk:
        raise ValidationError('Review the current submitted revision, not an older snapshot.')
    state=revision_state(revision)
    if state in {'returned','customer_rejected','approved'}:
        raise ValidationError('This revision already has a final review decision.')
    role=role_for(actor)
    l2=actor.pk==revision.l2_reviewer_id and role==(Profile.Roles.QUALITY_ENGINEER if revision.workflow_version==2 else Profile.Roles.TEAM_LEAD)
    l3=actor.pk==revision.l3_approver_id and role in ({Profile.Roles.TEAM_LEAD} if revision.workflow_version==2 else {Profile.Roles.ADMIN,Profile.Roles.PROJECT_MANAGER})
    if actor.pk==revision.submitted_by_id or not (l2 or l3):
        raise PermissionDenied('Administrative privilege cannot sign an independent technical stage.')
    if action not in {'validate','approve','return'}:
        raise ValidationError('Choose validate, approve or return.')
    if action=='validate' and (not l2 or state!='submitted') or action=='approve' and (not l3 or state!='validated'):
        raise PermissionDenied('The assigned independent review stage must be completed in order.')
    if action=='return' and not (l2 and state=='submitted' or l3 and state=='validated'):
        raise PermissionDenied('Only the currently assigned review stage may return this revision.')
    if not isinstance(reason,str) or len(reason)>4000 or action=='return' and not reason.strip():
        raise ValidationError('Returns require a recorded reason of at most 4000 characters.')
    if action!='return':
        if snapshot_digest(content_snapshot(checklist))!=revision.digest:
            raise ValidationError('Submitted inputs changed. Return this revision and submit a linked correction.')
        require_no_blocking_findings(checklist)
    if action=='validate':
        from .category_intake import record_qa_approval
        record_qa_approval(checklist,actor)
    decision=RevisionDecision.objects.create(revision=revision,action=action,level='L2' if l2 else 'L3',actor=actor,reason=reason.strip())
    if action=='return':
        checklist.status=Checklist.Status.REJECTED
        checklist.section_approvals={}
    elif action=='validate':
        checklist.status=Checklist.Status.REVIEW
    else:
        checklist.status=Checklist.Status.FINAL
        checklist.section_approvals={section['id']:{'by':actor.pk,'name':actor.username,'time':timezone.now().isoformat(),'revision_id':revision.pk} for section in revision.snapshot['schema']['sections']}
    checklist.review_history=[*(checklist.review_history or []),{'action':'revision_'+action,'revision_id':revision.pk,'level':decision.level,'reason':reason.strip(),'by':actor.pk,'name':actor.username,'time':timezone.now().isoformat()}]
    checklist.save(update_fields=['status','section_approvals','review_history','updated_at'])
    from .workflow_service import internal_review_completed
    if action=='approve':
        checklist.client_review_required=policy.customer_required
        checklist.client_review_routed_at=timezone.now()
        checklist.save(update_fields=['client_review_required','client_review_routed_at','updated_at'])
    internal_review_completed(checklist,actor)
    audit(actor,'revision_'+action,checklist.project,checklist_id=checklist.pk,revision_id=revision.pk,level=decision.level,reason=reason.strip())
    return decision


@transaction.atomic
def record_customer_decision(actor,checklist,decision,reason=''):
    """Record a named customer's decision against the exact approved revision.

    Caller may apply legacy closure first within its surrounding transaction.
    Returns the immutable decision; rejection persists the editable correction state.
    """
    from .review_route_service import route_for
    if route_for(checklist):raise ValidationError('Use the current token-bound review route Client action.')
    from .governance_views import lock_governance,audit
    lock_governance(actor)
    actor=_fresh_actor(actor)
    fresh=Checklist.objects.select_for_update().get(pk=checklist.pk)
    policy=policy_for(fresh)
    if not is_independent(fresh) or role_for(actor)!=Profile.Roles.CLIENT or not can_access_project(actor,fresh.project_id) or not policy or policy.customer_reviewer_id!=actor.pk or not policy.customer_required:
        raise PermissionDenied('Only the explicitly assigned Client may release or return this revision.')
    revision=policy.current_revision
    if not revision or revision_state(revision)!='approved' or fresh.status!=Checklist.Status.FINAL:
        raise ValidationError('Customer decisions require the current internally approved frozen revision.')
    if revision.decisions.filter(action__in=['customer_approve','customer_reject']).exists():
        raise ValidationError('This frozen revision already has a customer decision.')
    if decision not in {'approved','rejected'}:
        raise ValidationError('Choose approved or rejected.')
    if not isinstance(reason,str) or len(reason)>4000 or decision=='rejected' and not reason.strip():
        raise ValidationError('Customer returns require a recorded reason of at most4000 characters.')
    if decision=='approved' and snapshot_digest(content_snapshot(fresh))!=revision.digest:
        raise ValidationError('Approved inputs changed. Return this revision and submit a correction.')
    record=RevisionDecision.objects.create(revision=revision,action='customer_approve' if decision=='approved' else 'customer_reject',level='C1',actor=actor,reason=reason.strip())
    if decision=='rejected':
        fresh.status=Checklist.Status.REJECTED
        fresh.section_approvals={}
        fresh.client_review_completed_at=None
        fresh.save(update_fields=['status','section_approvals','client_review_completed_at','updated_at'])
        checklist.status=fresh.status
        checklist.section_approvals={}
        checklist.client_review_completed_at=None
        from .workflow_service import sync_assignment
        sync_assignment(fresh)
    audit(actor,'revision_customer_'+decision,fresh.project,checklist_id=fresh.pk,revision_id=revision.pk,reason=reason.strip())
    return record


def accessible_revision(actor,revision_id):
    if is_super_admin(actor):
        raise PermissionDenied('Super Admin cannot access engineering revision content.')
    revision=SubmissionRevision.objects.select_related('checklist').filter(pk=revision_id).first()
    if not revision:
        raise Http404()
    if role_for(actor)==Profile.Roles.CLIENT:
        policy=revision.snapshot.get('review_policy') or {}
        frozen_route=revision.snapshot.get('review_route_policy')
        if frozen_route:
            shared=revision.route_events.filter(from_stage='team_lead',to_stage='client').exists()
            if not can_access_project(actor,revision.checklist.project_id) or frozen_route.get('reviewers',{}).get('client')!=actor.pk or not shared:raise Http404()
        elif not can_access_project(actor,revision.checklist.project_id) or policy.get('customer_reviewer_id')!=actor.pk or revision_state(revision) not in {'approved','customer_rejected'}:
            raise Http404()
    elif not assigned_site_access(actor,revision.checklist):
        historical_role=(Profile.Roles.QUALITY_ENGINEER if revision.workflow_version==2 else Profile.Roles.TEAM_LEAD) if actor.pk==revision.l2_reviewer_id else (Profile.Roles.TEAM_LEAD if revision.workflow_version==2 else Profile.Roles.PROJECT_MANAGER) if actor.pk==revision.l3_approver_id else None
        permitted={Profile.Roles.ADMIN,Profile.Roles.PROJECT_MANAGER} if historical_role==Profile.Roles.PROJECT_MANAGER else {historical_role}
        if not historical_role or role_for(actor) not in permitted or not can_access_project(actor,revision.checklist.project_id):
            raise Http404()
    return revision
