"""Scoped, offline diagnostics and explicit owner maintenance decisions.

The website records an operator's bounded evidence, never executes candidate
code or treats an AI observation as engineering approval. Tests and PR claims
remain operator-attested; actual installation additionally checks this runtime.
"""
from copy import deepcopy
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Count, Q

from .access import _principal, _role, _company, accessible_projects
from .models import Checklist, GovernanceAudit, Profile
from .operations_service import release_id
from .support_models import SupportCase, SupportEvent, STATUS_CHOICES


SHA40 = re.compile(r'[a-f0-9]{40}')
SHA64 = re.compile(r'[a-f0-9]{64}')
MAX_RECEIPT_BYTES = 16384
RECEIPT_KEYS = {'format', 'case_id', 'report_sha256', 'base_commit', 'tested_commit',
                'patch_sha256', 'regression_sha256', 'test_evidence', 'pr_url',
                'provenance', 'candidate_only', 'owner_release_approved'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def principal(actor, owner=False):
    profile = _principal(actor)
    role = _role(profile)
    if role == Profile.Roles.SUPER_ADMIN:
        return profile, True
    if owner or role != Profile.Roles.ADMIN or _company(profile) is None:
        raise PermissionDenied('Current company administrator or platform-owner access is required.')
    return profile, False


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Use the request identifier supplied by the support form.') from None


def _scope(actor, project_id=None):
    profile, owner = principal(actor)
    projects = accessible_projects(actor)
    project = None
    if project_id not in (None, ''):
        if isinstance(project_id, bool):
            raise ValidationError('Choose a current accessible project.')
        try:
            project = projects.filter(pk=int(project_id)).select_related('company').first()
        except (ValueError, TypeError, OverflowError):
            project = None
        if project is None:
            raise PermissionDenied('Choose a current accessible project.')
        projects = projects.filter(pk=project.pk)
    return profile, owner, projects, project


def visible_cases(actor):
    profile, owner = principal(actor)
    cases = SupportCase.objects.select_related('company', 'project', 'created_by').prefetch_related('events')
    if owner:
        return cases
    return cases.filter(company_id=_company(profile)).filter(
        Q(project_id__in=accessible_projects(actor).values('pk')) |
        Q(project__isnull=True, created_by_id=actor.pk))


def get_case(actor, case_id, lock=False):
    query = visible_cases(actor)
    if lock:
        query = query.select_for_update()
    try:
        case = query.get(pk=_uuid(case_id))
    except SupportCase.DoesNotExist:
        raise PermissionDenied('The support report is unavailable in your current scope.') from None
    if digest(case.report) != case.report_digest:
        raise ValidationError('The retained support report does not match its saved digest.')
    return case


def _counts(query, allowed):
    result = {}
    for row in query.values('status').annotate(count=Count('pk')):
        key = row['status'] if row['status'] in allowed else 'other'
        result[key] = result.get(key, 0) + row['count']
    return result


def health(actor, project_id=None):
    from .photo_models import PhotoJob
    from .survey_processing_models import SurveyProcessingJob, SurveyUploadSession
    from .survey_processing import STAGES
    profile, owner, projects, project = _scope(actor, project_id)
    project_ids = projects.values('pk')
    tasks = Checklist.objects.filter(project_id__in=project_ids)
    photo_jobs = _counts(PhotoJob.objects.filter(checklist__project_id__in=project_ids),
                         {'queued', 'running', 'completed', 'failed', 'paused', 'pausing'})
    survey_jobs = _counts(SurveyProcessingJob.objects.filter(revision__checklist__project_id__in=project_ids), set(STAGES))
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        database_ok = cursor.fetchone() == (1,)
    media = getattr(settings, 'MEDIA_ROOT', None)
    storage_ok = bool(media and Path(media).is_dir() and os.access(media, os.R_OK | os.W_OK))
    counts = {'projects': projects.count(), 'tasks': tasks.count(), 'photo_jobs': photo_jobs,
              'survey_jobs': survey_jobs,
              'open_upload_sessions': SurveyUploadSession.objects.filter(
                  checklist__project_id__in=project_ids, finished_at__isnull=True).count()}
    scope = {'kind': 'platform' if owner and project is None else 'company',
             'company_id': project.company_id if project else (None if owner else _company(profile)),
             'project_id': project.pk if project else None}
    return {'format': 'isurvix-support-health-v1', 'scope': scope,
            'label': 'Platform administration' if scope['kind'] == 'platform' else 'Your accessible company projects',
            'release': release_id(), 'counts': counts,
            'metrics': [{'label': 'Accessible projects', 'value': counts['projects']},
                        {'label': 'Tasks', 'value': counts['tasks']},
                        {'label': 'Photo-processing jobs', 'value': sum(photo_jobs.values())},
                        {'label': 'Survey-processing jobs', 'value': sum(survey_jobs.values())},
                        {'label': 'Open upload sessions', 'value': counts['open_upload_sessions']}],
            'checks': [{'label': 'Database', 'status': 'available' if database_ok else 'unavailable'},
                       {'label': 'Evidence storage', 'status': 'available' if storage_ok else 'unavailable'},
                       {'label': 'AI connection', 'status': 'not checked'}]}


def _audit(case, actor, kind, status, sequence):
    GovernanceAudit.objects.create(actor=actor, actor_name=actor.get_username(), project=case.project,
        action='support.' + kind, details={'case_id': str(case.pk), 'report_sha256': case.report_digest,
                                        'status': status, 'sequence': sequence})


def _append(case, actor, key, input_digest, kind, status, details=None):
    sequence = case.version + 1
    SupportEvent.objects.create(case=case, actor=actor, request_key=key, input_digest=input_digest,
                                sequence=sequence, kind=kind, status=status, details=details or {})
    _audit(case, actor, kind, status, sequence)
    case._prefetched_objects_cache = {}
    return case


def _actor_lock(actor, owner=False):
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    principal(actor, owner=owner)
    return actor


def create_case(actor, *, category, description, project_id=None, request_key):
    key = _uuid(request_key)
    if category not in dict(SupportCase.CATEGORIES):
        raise ValidationError('Choose a supported issue category.')
    if not isinstance(description, str) or not description.strip() or len(description) > 2000:
        raise ValidationError('Describe the issue in 1 to 2000 characters; omit passwords and credentials.')
    description = description.strip()
    with transaction.atomic():
        actor = _actor_lock(actor)
        profile, owner, projects, project = _scope(actor, project_id)
        company_id = project.company_id if project else (None if owner else _company(profile))
        request_digest = digest({'actor': actor.pk, 'company': company_id, 'project': project.pk if project else None,
                                 'category': category, 'description': description})
        existing = SupportCase.objects.filter(request_key=key).first()
        if existing:
            if existing.request_digest != request_digest or existing.created_by_id != actor.pk:
                raise ValidationError('This request identifier already belongs to different support inputs.')
            return get_case(actor, existing.pk)
        report = health(actor, project.pk if project else None)
        case = SupportCase.objects.create(request_key=key, request_digest=request_digest, company_id=company_id,
            project=project, created_by=actor, category=category, description=description,
            source_release=report['release'], report=report, report_digest=digest(report))
        return _append(case, actor, key, request_digest, 'reported', 'reported')


def export_bundle(actor, case_id):
    case = get_case(actor, case_id)
    manifest = {'format': 'isurvix-support-diagnostics-v1', 'case_id': str(case.pk),
                'report_sha256': case.report_digest, 'source_release': case.source_release}
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', canonical(manifest))
        archive.writestr('diagnostics.json', canonical(case.report))
    return output.getvalue()


def _repo():
    value = getattr(settings, 'ISURVIX_SUPPORT_REPOSITORY', 'assimbaig/iSurvix-Field')
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value):
        raise ValidationError('The support repository is not configured.')
    return value


def validate_pr_url(value):
    if not isinstance(value, str) or not re.fullmatch(re.escape('https://github.com/' + _repo() + '/pull/') + r'[1-9][0-9]{0,9}', value):
        raise ValidationError('Use the exact pull-request URL from the configured support repository.')
    return value


def _strict_receipt(case, receipt):
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        raise ValidationError('Use the complete bounded operator repair receipt.')
    try:
        if len(canonical(receipt)) > MAX_RECEIPT_BYTES:
            raise ValueError()
        if receipt['format'] != 'isurvix-support-repair-v1' or _uuid(receipt['case_id']) != case.pk:
            raise ValueError()
        if receipt['report_sha256'] != case.report_digest or receipt['base_commit'] != case.source_release:
            raise ValueError()
        for field in ('base_commit', 'tested_commit'):
            if not isinstance(receipt[field], str) or not SHA40.fullmatch(receipt[field]):
                raise ValueError()
        if receipt['base_commit'] == receipt['tested_commit']:
            raise ValueError()
        for field in ('report_sha256', 'patch_sha256', 'regression_sha256'):
            if not isinstance(receipt[field], str) or not SHA64.fullmatch(receipt[field]):
                raise ValueError()
        evidence = receipt['test_evidence']
        if not isinstance(evidence, dict) or set(evidence) != {'baseline_failed', 'patched_passed', 'unit_passed', 'integration_passed', 'isolation', 'execution_id'}:
            raise ValueError()
        if any(evidence[key] is not True for key in ('baseline_failed', 'patched_passed', 'unit_passed', 'integration_passed')):
            raise ValueError()
        if evidence['isolation'] != 'docker-no-network':
            raise ValueError()
        _uuid(evidence['execution_id'])
        if receipt['provenance'] != 'operator-attested' or receipt['candidate_only'] is not True or receipt['owner_release_approved'] is not False:
            raise ValueError()
        if receipt['pr_url']:
            validate_pr_url(receipt['pr_url'])
        elif not isinstance(receipt['pr_url'], str):
            raise ValueError()
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise ValidationError('The operator receipt does not match this report, source or required test evidence.') from None
    return deepcopy(receipt)


def _version(case, expected):
    if isinstance(expected, bool):
        raise ValidationError('Reload the current support version.', code='conflict')
    try:
        valid = int(expected) == case.version and str(expected).isdigit()
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValidationError('The support history changed. Reload before recording this action.', code='conflict')


def _replay(case, actor, key, input_digest):
    previous = case.events.filter(request_key=key).first()
    if previous:
        if previous.actor_id != actor.pk or previous.input_digest != input_digest:
            raise ValidationError('This action identifier belongs to different support inputs.')
        return True
    return False


def _receipt(case):
    event = case.events.filter(kind='receipt_recorded').order_by('-sequence').first()
    if event is None:
        raise ValidationError('Record an isolated operator test receipt before approving a repair.')
    return event.details['receipt']


def import_receipt(actor, case_id, *, receipt, expected_version, request_key):
    key = _uuid(request_key)
    with transaction.atomic():
        actor = _actor_lock(actor, owner=True)
        case = get_case(actor, case_id, lock=True)
        receipt = _strict_receipt(case, receipt)
        input_digest = digest({'kind': 'receipt_recorded', 'receipt': receipt})
        if _replay(case, actor, key, input_digest):
            return case
        existing = case.events.filter(kind='receipt_recorded').filter(input_digest=input_digest).first()
        if existing:
            return case
        _version(case, expected_version)
        if case.status not in {'repair_requested', 'changes_requested'}:
            raise ValidationError('Request an isolated repair before recording its operator evidence.')
        return _append(case, actor, key, input_digest, 'receipt_recorded',
                       'pr_ready' if receipt['pr_url'] else 'tests_passed', {'receipt': receipt})


ACTION_LABELS = {'request_repair': 'Request isolated repair', 'link_pr': 'Record pull request',
                 'approve_repair': 'Approve tested repair', 'approve_release': 'Approve exact release',
                 'confirm_installed': 'Confirm installed release', 'request_changes': 'Request changes', 'cancel': 'Cancel report'}
ACTION_STATES = {'reported': ['request_repair', 'cancel'],
                 'repair_requested': ['cancel'], 'changes_requested': ['cancel'],
                 'tests_passed': ['link_pr', 'request_changes', 'cancel'],
                 'pr_ready': ['approve_repair', 'request_changes', 'cancel'],
                 'repair_approved': ['approve_release', 'request_changes'],
                 'release_approved': ['confirm_installed']}


def allowed_actions(actor, case):
    principal(actor)
    _profile, owner = principal(actor)
    if not owner:
        return []
    return [{'value': action, 'label': ACTION_LABELS[action],
             'help': 'Records a human maintenance decision. It does not execute code or approve engineering work.',
             'needs_reason': action in {'request_changes', 'cancel'}, 'needs_pr_url': action == 'link_pr'}
            for action in ACTION_STATES.get(case.status, [])]


def change_case(actor, case_id, *, action, expected_version, request_key, reason='', pr_url=''):
    key = _uuid(request_key)
    if action not in ACTION_LABELS:
        raise ValidationError('Choose an available support action.')
    if not isinstance(reason, str) or len(reason) > 500:
        raise ValidationError('Keep the support reason within 500 characters.')
    reason = reason.strip()
    if action in {'request_changes', 'cancel'} and not reason:
        raise ValidationError('Describe why this action is needed.')
    if action != 'link_pr' and pr_url:
        raise ValidationError('A pull-request reference belongs only to the record-PR action.')
    with transaction.atomic():
        actor = _actor_lock(actor, owner=True)
        case = get_case(actor, case_id, lock=True)
        input_digest = digest({'kind': action, 'reason': reason, 'pr_url': pr_url})
        if _replay(case, actor, key, input_digest):
            return case
        _version(case, expected_version)
        if action not in ACTION_STATES.get(case.status, []):
            raise ValidationError('This action is not available at the current support stage.')
        details = {'reason': reason}
        if action == 'request_repair':
            if not SHA40.fullmatch(case.source_release):
                raise ValidationError('An exact installed source release is required before requesting a repair.')
            status = 'repair_requested'
        elif action == 'link_pr':
            details['pr_url'] = validate_pr_url(pr_url)
            details['tested_commit'] = _receipt(case)['tested_commit']
            status = 'pr_ready'
        elif action in {'approve_repair', 'approve_release', 'confirm_installed'}:
            receipt = _receipt(case)
            details.update(tested_commit=receipt['tested_commit'], report_sha256=case.report_digest)
            if action == 'approve_repair':
                status = 'repair_approved'
            elif action == 'approve_release':
                approved = case.events.filter(kind='approve_repair').order_by('-sequence').first()
                if not approved or approved.details.get('tested_commit') != receipt['tested_commit']:
                    raise ValidationError('Approve this exact tested repair before approving its release.')
                status = 'release_approved'
            else:
                approved = case.events.filter(kind='approve_release').order_by('-sequence').first()
                if not approved or approved.details.get('tested_commit') != receipt['tested_commit'] or release_id() != receipt['tested_commit']:
                    raise ValidationError('The approved exact release is not installed on this server.')
                details['installed_release'] = release_id()
                status = 'installed'
        elif action == 'request_changes':
            status = 'changes_requested'
        else:
            status = 'cancelled'
        return _append(case, actor, key, input_digest, action, status, details)


def _refs(details):
    refs = []
    receipt = details.get('receipt', {})
    values = {**receipt, **details}
    for field, label in [('report_sha256', 'Report SHA256'), ('base_commit', 'Source commit'),
                         ('tested_commit', 'Tested commit'), ('patch_sha256', 'Patch SHA256'),
                         ('regression_sha256', 'Regression SHA256'), ('installed_release', 'Installed release')]:
        value = values.get(field)
        if value:
            refs.append({'label': label, 'value': value, 'provenance': 'Server release checked' if field == 'installed_release' else 'Operator-attested' if receipt else 'Human decision'})
    if values.get('pr_url'):
        refs.append({'label': 'Pull request', 'value': values['pr_url'], 'url': values['pr_url'], 'provenance': 'Operator-attested'})
    return refs


def history_rows(case):
    return [{'sequence': event.sequence, 'created_at': event.created_at,
             'label': ACTION_LABELS.get(event.kind, {'reported': 'Report saved', 'receipt_recorded': 'Operator test receipt recorded'}.get(event.kind, 'Support event')),
             'status': event.status, 'status_label': dict(STATUS_CHOICES).get(event.status, 'Unknown'),
             'actor_label': event.actor.get_username(), 'summary': event.details.get('reason', ''),
             'references': _refs(event.details)}
            for event in case.events.select_related('actor').order_by('sequence')]


def case_references(case):
    found = {}
    for event in case.events.order_by('sequence'):
        for reference in _refs(event.details):
            found[(reference['label'], reference['value'])] = reference
    return list(found.values())
