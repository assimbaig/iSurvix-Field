"""Durable notifications from saved workflow events; no request-time network.

Email links require the existing application login and authorization. Internal
remarks, AI findings, evidence bytes and bearer links never enter these emails.
The outbox records notification delivery, never an engineering decision.
"""
from datetime import timedelta, timezone as utc
import hashlib
from types import SimpleNamespace
from urllib.parse import urlencode
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.signals import post_save, pre_save
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from .access import can_access_project, company_id_for, role_for, users_for_project
from .invitation_email import _public_origin
from .models import Checklist, GovernanceAudit, Profile, Project, WorkAssignment, WorkflowEmailDelivery
from .notification_email import GraphMailClient, NotificationEmailError


MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


class RecipientUnavailable(Exception):
    pass
OPERATIONAL_ROLES = {Profile.Roles.ADMIN, Profile.Roles.TEAM_LEAD, Profile.Roles.QUALITY_ENGINEER,
                     Profile.Roles.ENGINEER, Profile.Roles.CLIENT}
_SUBMISSIONS = {'category_evidence_submitted', 'survey_submitted', 'revision_submitted', 'review_route_submit'}
_APPROVALS = {'quality_approve', 'revision_validate', 'revision_approve', 'revision_customer_approved',
              'review_route_approve'}
_REJECTIONS = {'quality_reject', 'revision_return', 'revision_customer_rejected', 'review_route_reject', 'review_route_return'}


def enabled():
    return bool(getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', False)
                and getattr(settings, 'WORKFLOW_NOTIFICATION_EMAIL_ENABLED', False))


def _site_access(user, checklist):
    try:
        from .template_views import survey_access
        survey_access(SimpleNamespace(user=user), checklist.pk)
        return True
    except (Http404, PermissionDenied, ValidationError):
        return False


def _eligible(user, project, expected_role=None):
    role = role_for(user)
    return bool(role in OPERATIONAL_ROLES and (expected_role is None or role == expected_role)
        and company_id_for(user) == project.company_id and can_access_project(user, project.pk))


def _project_users(project, roles=OPERATIONAL_ROLES):
    ids = set(users_for_project(project, roles).values_list('pk', flat=True))
    if project.administrator_id and Profile.Roles.ADMIN in roles:
        ids.add(project.administrator_id)
    return User.objects.select_related('profile').filter(pk__in=ids).order_by('pk')


def _stage_users(checklist, stage):
    role = {'engineer': Profile.Roles.ENGINEER, 'quality_engineer': Profile.Roles.QUALITY_ENGINEER,
            'team_lead': Profile.Roles.TEAM_LEAD, 'client': Profile.Roles.CLIENT}.get(stage)
    if role is None:
        return set()
    ids = None
    if checklist.governance_mode == 'independent':
        from .review_route_service import route_for
        from .independent_workflow import policy_for
        route = route_for(checklist)
        policy = policy_for(checklist)
        if route:
            ids = {route.reviewers.get(stage)}
        elif policy:
            ids = {'engineer': {checklist.user_id}, 'quality_engineer': {policy.l2_reviewer_id} if policy.workflow_version == 2 else set(),
                'team_lead': {policy.l3_approver_id if policy.workflow_version == 2 else policy.l2_reviewer_id},
                'client': {policy.customer_reviewer_id}}.get(stage, set())
        else:
            ids = {checklist.user_id} if stage == 'engineer' else set()
    elif stage in {'engineer', 'quality_engineer'}:
        ids = {checklist.user_id if stage == 'engineer' else checklist.quality_reviewer_id}
    users = User.objects.filter(pk__in=[value for value in ids if value]) if ids is not None else _project_users(checklist.project, {role})
    return {user.pk for user in users if role_for(user) == role
            and _eligible(user, checklist.project) and _site_access(user, checklist)}


def _kind(audit):
    if not isinstance(audit.details, dict):
        return None
    from .custom_notifications import PROJECT_ACTIONS,COMPANY_ACTIONS
    if audit.action in COMPANY_ACTIONS and audit.project_id is None:
        return 'company_update'
    if audit.action in PROJECT_ACTIONS:
        return 'project_update'
    if audit.action in _SUBMISSIONS:
        return 'submission'
    if audit.action in _APPROVALS:
        return 'approval'
    if audit.action in _REJECTIONS:
        return 'rejection'
    if audit.action == 'survey_review':
        return {'approve': 'approval', 'partial': 'approval', 'reject': 'rejection', 'changes': 'rejection'}.get(audit.details.get('decision'))
    if audit.action == 'client_decision_recorded':
        return {'approved': 'approval', 'rejected': 'rejection'}.get((audit.details.get('decision') or {}).get('decision'))
    if audit.action == 'client_review_routed' and audit.details.get('client_review_required'):
        return 'client_review'
    if audit.action in {'task_assigned', 'task_assignment_changed', 'quality_assigned'}:
        return 'assignment'
    return None


def _audit(delivery, action):
    GovernanceAudit.objects.create(action='workflow_email.' + action, project=delivery.project,
        details={'delivery_id': str(delivery.pk), 'event_key': delivery.event_key,
                 'recipient_id': delivery.recipient_id, 'kind': delivery.kind,
                 'status': delivery.status, 'attempts': delivery.attempts, 'code': delivery.error_code})


@transaction.atomic
def _queue(project, recipient, *, event_key, kind, checklist=None, source_audit=None,
           source_processing_event=None, drawing_set=None, digest_day=None, assignment=None):
    if not _eligible(recipient, project) or checklist is not None and not _site_access(recipient, checklist):
        return None
    signature = hashlib.sha256(f'{event_key}:{recipient.pk}'.encode()).hexdigest()
    delivery, created = WorkflowEmailDelivery.objects.get_or_create(dedupe_key=signature, defaults={
        'event_key': event_key, 'kind': kind, 'project': project, 'company_id': project.company_id,
        'checklist': checklist, 'recipient': recipient, 'expected_role': role_for(recipient),
        'assignment': assignment,
        'source_audit': source_audit, 'source_processing_event': source_processing_event,
        'drawing_set': drawing_set, 'digest_day': digest_day})
    if created:
        _audit(delivery, 'queued')
    elif source_audit is not None and delivery.source_audit_id is None:
        WorkflowEmailDelivery.objects.filter(pk=delivery.pk, source_audit__isnull=True).update(source_audit=source_audit)
    return delivery if created else None


@transaction.atomic
def queue_assignment(work, audit=None):
    if not enabled() or not work.pk:
        return 0
    work = WorkAssignment.objects.select_related('project', 'checklist__project', 'assigned_to').get(pk=work.pk)
    if work.checklist_id and (work.project_id != work.checklist.project_id or work.assigned_to_id != work.checklist.user_id):
        return 0
    if audit is None or audit.action != 'task_assignment_changed':
        audit = GovernanceAudit.objects.filter(action='task_assignment_changed', project=work.project,
            details__assignment_id=work.pk, details__recipient_id=work.assigned_to_id).order_by('-pk').first()
    if audit is None:
        return 0
    return int(_queue(work.project, work.assigned_to,
        event_key=f'assignment-event:{audit.pk}', kind='assignment', assignment=work,
        checklist=work.checklist, source_audit=audit) is not None)


@transaction.atomic
def queue_audit_event(source):
    if not enabled() or not source.pk:
        return 0
    audit = GovernanceAudit.objects.select_related('project').filter(pk=source.pk).first()
    if audit is None or not isinstance(audit.details, dict):
        return 0
    kind = _kind(audit)
    if kind == 'company_update':
        from .custom_notifications import queue_company_event
        return queue_company_event(audit)
    if kind is None or audit.project_id is None:
        return 0
    if audit.action in {'task_assigned', 'task_assignment_changed'}:
        assignment = WorkAssignment.objects.filter(pk=audit.details.get('assignment_id'), project=audit.project).first()
        return queue_assignment(assignment, audit) if assignment else 0
    if kind == 'project_update':
        recipients=set(_project_users(audit.project,{Profile.Roles.ADMIN}).values_list('pk',flat=True))
        target=audit.details.get('user_id') or audit.details.get('administrator_id')
        if type(target) is int:recipients.add(target)
        return sum(_queue(audit.project,user,event_key=f'audit:{audit.pk}',kind=kind,source_audit=audit) is not None for user in User.objects.filter(pk__in=recipients))
    checklist = Checklist.objects.select_related('project').filter(pk=audit.details.get('checklist_id'), project_id=audit.project_id).first()
    if checklist is None:
        return 0
    from .category_intake import enabled as category_enabled
    if audit.action in {'revision_submitted', 'review_route_submit'} and category_enabled(checklist):
        return 0  # One submission also emits its category handoff; notify once.
    if audit.action == 'client_decision_recorded' and checklist.governance_mode == 'independent':
        return 0  # The immutable revision customer decision is the source.
    from .workflow_service import workflow_stage
    if kind == 'submission':
        ids = _stage_users(checklist, workflow_stage(checklist))
    elif kind == 'assignment':
        ids = {audit.details.get('reviewer_id')}
    elif kind == 'client_review':
        ids = _stage_users(checklist, 'client')
    else:
        ids = {checklist.user_id, checklist.project.administrator_id}
        ids |= _stage_users(checklist, 'team_lead')
        ids |= _stage_users(checklist, workflow_stage(checklist))
    ids.discard(audit.actor_id)
    return sum(_queue(checklist.project, user, event_key=f'audit:{audit.pk}', kind=kind,
               checklist=checklist, source_audit=audit) is not None
               for user in User.objects.filter(pk__in=[value for value in ids if value]))


@transaction.atomic
def queue_processing_event(event):
    if not enabled() or event.action not in {'technical_approve', 'technical_reject'}:
        return 0
    c = event.revision.checklist
    ids = {c.user_id} if event.action == 'technical_reject' else _stage_users(c, 'team_lead')
    ids.discard(event.actor_id)
    return sum(_queue(c.project, user, event_key=f'processing:{event.pk}',
        kind='rejection' if event.action == 'technical_reject' else 'approval',
        checklist=c, source_processing_event=event) is not None
        for user in User.objects.filter(pk__in=ids))


@transaction.atomic
def queue_drawing_event(asset):
    if not enabled():
        return 0
    c = asset.revision.checklist
    ids = {c.project.administrator_id}
    for stage in ('engineer', 'quality_engineer', 'team_lead', *(['client'] if asset.released else [])):
        ids |= _stage_users(c, stage)
    return sum(_queue(c.project, user, event_key=f'drawing:{asset.pk}',
        kind='report_released' if asset.released else 'report_ready', checklist=c, drawing_set=asset) is not None
        for user in User.objects.filter(pk__in=[value for value in ids if value]))


def _visible_checklists(user, project):
    role = role_for(user)
    from .task_explorer import scopes
    _, checklists, _ = scopes(user)
    qs = checklists.filter(project=project)
    if role == Profile.Roles.ENGINEER:
        return qs.filter(user=user)
    if role == Profile.Roles.QUALITY_ENGINEER:
        return qs.filter(Q(governance_mode='legacy', quality_reviewer=user)
            | Q(governance_mode='independent', review_policy__workflow_version=2, review_policy__l2_reviewer=user)).distinct()
    if role == Profile.Roles.TEAM_LEAD:
        return qs.filter(Q(governance_mode='legacy')
            | Q(governance_mode='independent', review_policy__workflow_version=2, review_policy__l3_approver=user)
            | Q(governance_mode='independent', review_policy__workflow_version=1, review_policy__l2_reviewer=user)).distinct()
    if role == Profile.Roles.CLIENT:
        from .access import client_checklist_visibility
        return qs.filter(client_checklist_visibility(user)).filter(
            Q(review_route_record__isnull=True) | Q(review_route_record__reviewers__client=user.pk)).distinct()
    return qs if role == Profile.Roles.ADMIN else qs.none()


def _visible_unstarted(user, project):
    from .task_explorer import scopes
    return scopes(user)[2].filter(project=project)


def queue_daily_digests(now=None):
    now = (now or timezone.now()).astimezone(utc.utc)
    hour = getattr(settings, 'WORKFLOW_EMAIL_DAILY_HOUR', 15)
    if not enabled() or not getattr(settings, 'WORKFLOW_EMAIL_DAILY_ENABLED', True):
        return 0
    from .custom_notifications import queue_combined
    from .models import CompanyNotificationSettings
    count = queue_combined(now)
    if now.hour < hour:return count
    combined_companies=CompanyNotificationSettings.objects.filter(combined_daily_enabled=True).values_list('company_id',flat=True)
    for project in Project.objects.exclude(company_id__in=combined_companies).order_by('pk').iterator(chunk_size=50):
        already = set(WorkflowEmailDelivery.objects.filter(kind='daily', project=project,
            digest_day=now.date()).values_list('recipient_id', flat=True))
        for user in _project_users(project).iterator(chunk_size=100):
            if user.pk in already or not _eligible(user, project) or not (
                    _visible_checklists(user, project).exists() or _visible_unstarted(user, project).exists()):
                continue
            count += _queue(project, user, event_key=f'daily:{now.date().isoformat()}:{project.pk}',
                kind='daily', digest_day=now.date()) is not None
    return count


def _fresh(delivery):
    if delivery.kind == 'company_update':
        from .custom_notifications import company_event_context
        return company_event_context(delivery)
    if delivery.kind == 'daily_combined':
        from .custom_notifications import combined_context
        return combined_context(delivery)
    if not delivery.project_id or not delivery.recipient_id:
        return None
    project = Project.objects.filter(pk=delivery.project_id).first()
    user = User.objects.select_related('profile').filter(pk=delivery.recipient_id).first()
    if project is None or user is None or project.company_id != delivery.company_id or not _eligible(user, project, delivery.expected_role):
        return None
    try:
        validate_email(user.email)
    except ValidationError:
        return None
    if '\r' in user.email or '\n' in user.email:
        return None
    if delivery.kind == 'project_update':
        return (user, project, None) if GovernanceAudit.objects.filter(pk=delivery.source_audit_id,project=project).exists() else None
    if delivery.kind == 'daily':
        from .models import CompanyNotificationSettings
        if CompanyNotificationSettings.objects.filter(company_id=project.company_id,combined_daily_enabled=True).exists():return None
        return (user, project, None) if (_visible_checklists(user, project).exists()
            or _visible_unstarted(user, project).exists()) else None
    if delivery.kind == 'assignment' and delivery.assignment_id is not None:
        work = WorkAssignment.objects.select_related('checklist__project').filter(
            pk=delivery.assignment_id, project=project, assigned_to=user).first()
        if work is None:
            return None
        if work.checklist_id and not _site_access(user, work.checklist):
            return None
        return user, project, work.checklist
    checklist = Checklist.objects.select_related('project').filter(pk=delivery.checklist_id, project=project).first()
    if checklist is None or not _site_access(user, checklist):
        return None
    if delivery.kind == 'assignment' and not GovernanceAudit.objects.filter(
            pk=delivery.source_audit_id, action='quality_assigned', project=project,
            details__checklist_id=checklist.pk, details__reviewer_id=user.pk).exists():
        return None
    return user, project, checklist


def _compact(value, maximum=130):
    return ' '.join(str(value).split())[:maximum]


def _report_url(user, checklist, asset):
    from .survey_processing_views import output
    # Use the exact existing download authorization/integrity checks, including
    # current-revision/release gates for Clients. Do not email file paths/bytes.
    response = output(SimpleNamespace(user=user, method='GET'), checklist.pk, asset.pk, 0, 'pdf')
    try:
        if response.status_code != 200:
            raise Http404()
    finally:
        response.close()
    return reverse('survey_processing_output', args=[checklist.pk, asset.pk, 0, 'pdf'])


def _default_message(delivery, user, project, checklist):
    origin = _public_origin()
    if delivery.kind == 'daily_combined':
        from .custom_notifications import combined_message
        return combined_message(delivery,user)
    if delivery.kind == 'company_update':
        return 'Company account or client change', '\n'.join(['A company administrative action was recorded.',f'Company: {_compact(delivery.company.name)}',f'Action: {_compact(delivery.source_audit.action)}','Open company records (sign-in required): '+origin+reverse('governance_home'),'This notification does not change permissions or approve engineering work.'])
    if delivery.kind == 'project_update':
        return 'Project or access change ? '+_compact(project.name,100), '\n'.join(['An administrative project action was recorded.',f'Project: {_compact(project.name)}',f'Action: {_compact(delivery.source_audit.action)}','Open permitted project records: '+origin+reverse('governance_home')+'?project='+str(project.pk),'This notification does not change permissions or approve engineering work.'])
    if delivery.kind == 'daily':
        rows = _visible_checklists(user, project)
        counts = {entry['status']: entry['n'] for entry in rows.values('status').annotate(n=Count('pk'))}
        unstarted = _visible_unstarted(user, project).count()
        body = [f'Daily iField report for {delivery.digest_day:%Y-%m-%d} UTC.',
            f'Project: {_compact(project.name)}', f'Current visible tasks: {sum(counts.values()) + unstarted}.',
            f'Unstarted assignments: {unstarted}.']
        body.extend(f'{label}: {counts.get(status, 0)}' for status, label in Checklist.Status.choices)
        body.extend(['', 'Sign in to view your permitted tasks:', origin + reverse('governance_tasks') + f'?project={project.pk}'])
        return 'Daily iField report — ' + _compact(project.name, 100), '\n'.join(body)
    if delivery.kind == 'assignment' and checklist is None:
        work = WorkAssignment.objects.get(pk=delivery.assignment_id, project=project, assigned_to=user)
        link = origin + reverse('governance_tasks') + '?' + urlencode({'project': project.pk, 'q': work.site_id})
        return 'Task assigned — ' + _compact(work.site_id, 100), '\n'.join([
            'Task assigned.', f'Project: {_compact(project.name)}', f'Site ID: {_compact(work.site_id)}',
            'Sign in to open your assigned task:', link,
            'This notification does not change or approve engineering work.'])
    titles = {'assignment': 'Task assigned', 'submission': 'Submission available for review',
              'approval': 'Workflow approval recorded', 'rejection': 'Task returned for correction',
              'client_review': 'Client review requested', 'report_ready': 'Draft report ready for review',
              'report_released': 'Approved report released'}
    title = titles[delivery.kind]
    body = [title + '.', f'Project: {_compact(project.name)}', f'Site ID: {_compact(checklist.site_id or checklist.pk)}',
        'Notification event time (UTC): ' + delivery.created_at.astimezone(utc.utc).strftime('%Y-%m-%d %H:%M'),
        f'Current checklist status: {checklist.get_status_display()}.', '',
        'Sign in to view this task:', origin + reverse('custom_checklist', args=[checklist.pk])]
    if delivery.drawing_set_id:
        from .survey_processing_models import SurveyDrawingSet
        asset = SurveyDrawingSet.objects.select_related('revision').get(pk=delivery.drawing_set_id, revision__checklist=checklist)
        if (delivery.kind == 'report_released') != asset.released:
            raise Http404()
        body += ['', 'Full report PDF (authenticated access):', origin + _report_url(user, checklist, asset),
                 f'Survey processing revision {asset.revision.number}, drawing edition {asset.edition}.']
    elif delivery.kind == 'approval':
        from .workflow_service import closed_activity
        if closed_activity(checklist) and checklist.status == Checklist.Status.FINAL:
            from .independent_workflow import policy_for
            policy = policy_for(checklist)
            if policy and policy.current_revision_id:
                body += ['', 'Approved checklist report:', origin + reverse('roadmap_revision_report', args=[checklist.pk, policy.current_revision_id])]
            elif checklist.governance_mode == 'legacy':
                body += ['', 'Approved checklist workbook:', origin + reverse('custom_checklist_download', args=[checklist.pk])]
    body += ['', 'This notification does not change or approve engineering work.']
    return title + ' — ' + _compact(checklist.site_id or checklist.pk, 100), '\n'.join(body)


def _message(delivery,user,project,checklist):
    from .custom_notifications import custom_message
    subject,body=_default_message(delivery,user,project,checklist)
    return custom_message(delivery,user,project,checklist,subject,body)


def _finish(delivery, status, code=''):
    with transaction.atomic():
        current = WorkflowEmailDelivery.objects.select_for_update().filter(pk=delivery.pk,
            status='sending', lease_id=delivery.lease_id).first()
        if current is None:
            return
        current.status = status; current.error_code = code
        current.lease_id = None; current.lease_expires_at = None
        if status == 'accepted':
            current.accepted_at = timezone.now()
        elif status == 'queued':
            current.available_at = timezone.now() + timedelta(seconds=30 * current.attempts)
        current.save(update_fields=['status', 'error_code', 'lease_id', 'lease_expires_at', 'accepted_at', 'available_at', 'updated_at'])
        _audit(current, status)


@transaction.atomic
def recover_interrupted_workflow_emails():
    if not enabled():
        return 0
    count = 0
    for job in WorkflowEmailDelivery.objects.select_for_update().filter(status='sending', lease_expires_at__lte=timezone.now()):
        job.status = 'uncertain'; job.error_code = 'worker_interrupted'; job.lease_id = None; job.lease_expires_at = None
        job.save(update_fields=['status', 'error_code', 'lease_id', 'lease_expires_at', 'updated_at'])
        _audit(job, 'interrupted'); count += 1
    return count


@transaction.atomic
def retry_failed_workflow_emails():
    if not enabled():
        return 0
    count = 0
    for job in WorkflowEmailDelivery.objects.select_for_update().filter(status='failed'):
        job.status = 'queued'; job.attempts = 0; job.error_code = ''; job.available_at = timezone.now()
        job.save(update_fields=['status', 'attempts', 'error_code', 'available_at', 'updated_at'])
        _audit(job, 'retry'); count += 1
    return count


def process_next_workflow_email():
    if not enabled():
        return False
    recover_interrupted_workflow_emails()
    with transaction.atomic():
        job = WorkflowEmailDelivery.objects.select_for_update().filter(status='queued',
            available_at__lte=timezone.now(), attempts__lt=MAX_ATTEMPTS).first()
        if job is None:
            return False
        job.status = 'sending'; job.attempts += 1; job.lease_id = uuid.uuid4()
        job.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
        job.save(update_fields=['status', 'attempts', 'lease_id', 'lease_expires_at', 'updated_at'])
        _audit(job, 'started')
    try:
        context = _fresh(job)
        if context is None:
            _finish(job, 'cancelled', 'recipient_unavailable'); return True
        user, project, checklist = context
        subject, body = _message(job, user, project, checklist)
        def before_send():
            latest = _fresh(job)
            if latest is None:
                raise RecipientUnavailable()
            latest_user, latest_project, latest_checklist = latest
            if latest_user.email != user.email:
                # OAuth did not send a message. Requeue for the newly saved
                # address rather than using the old recipient snapshot.
                raise NotificationEmailError('recipient_changed', retryable=True)
            latest_subject, latest_body = _message(job, latest_user, latest_project, latest_checklist)
            return latest_user.email, latest_subject, latest_body
        GraphMailClient().send(user.email, subject, body, before_send=before_send)
    except RecipientUnavailable:
        _finish(job, 'cancelled', 'recipient_unavailable')
    except (Http404, PermissionDenied, ValidationError):
        _finish(job, 'cancelled', 'content_unavailable')
    except NotificationEmailError as error:
        status = 'uncertain' if error.uncertain else 'queued' if error.retryable and job.attempts < MAX_ATTEMPTS else 'failed'
        _finish(job, status, error.code)
    except Exception:
        _finish(job, 'uncertain', 'unexpected_delivery_failure')
    else:
        _finish(job, 'accepted')
    return True


def _saved_audit(sender, instance, created, raw=False, using='default', **kwargs):
    if created and not raw and using == 'default' and enabled() and _kind(instance) is not None:
        queue_audit_event(instance)


def _saved_processing(sender, instance, created, raw=False, using='default', **kwargs):
    if created and not raw and using == 'default':
        queue_processing_event(instance)


def _saved_drawing(sender, instance, created, raw=False, using='default', **kwargs):
    if created and not raw and using == 'default':
        queue_drawing_event(instance)


def _assignment_before_save(sender, instance, raw=False, using='default', **kwargs):
    if not raw and using == 'default' and enabled():
        instance._workflow_mail_previous = WorkAssignment.objects.filter(pk=instance.pk).values(
            'assigned_to_id', 'project_id').first() if instance.pk else None


def _saved_assignment(sender, instance, created, raw=False, using='default', **kwargs):
    if raw or using != 'default' or not enabled():
        return
    previous = getattr(instance, '_workflow_mail_previous', None)
    changed = created or previous is not None and (
        previous['assigned_to_id'] != instance.assigned_to_id or previous['project_id'] != instance.project_id)
    if changed:
        # This is an actual persisted assignment transition. A system audit row
        # supplies its stable identity, including A→B→A transitions; subsequent
        # business audits/checklist-link saves reuse it rather than resend.
        with transaction.atomic():
            GovernanceAudit.objects.create(action='task_assignment_changed', project=instance.project,
                details={'assignment_id': instance.pk, 'recipient_id': instance.assigned_to_id,
                    'previous_recipient_id': previous['assigned_to_id'] if previous else None,
                    'checklist_id': instance.checklist_id})


def install_receivers():
    from .survey_processing_models import SurveyDrawingSet, SurveyProcessingEvent
    for sender, receiver, name in [(GovernanceAudit, _saved_audit, 'audit'),
            (SurveyProcessingEvent, _saved_processing, 'processing'),
            (SurveyDrawingSet, _saved_drawing, 'drawing'), (WorkAssignment, _saved_assignment, 'assignment')]:
        post_save.connect(receiver, sender=sender, weak=False, dispatch_uid='workflow-email-v1-' + name)
    pre_save.connect(_assignment_before_save, sender=WorkAssignment, weak=False, dispatch_uid='workflow-email-v1-assignment-before')
