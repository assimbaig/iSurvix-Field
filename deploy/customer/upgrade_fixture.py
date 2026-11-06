"""Synthetic CI-only upgrade evidence and read-only retained-row comparisons.

Never seed an operational database. The guard requires both the disposable
environment flag and a pristine database with exactly the synthetic CI owner.
"""
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3


EXCLUDED = {'django_migrations', 'django_session', 'core_serverupdaterequest', 'core_serverupdateevent'}


def _identifier(value):
    return '"' + value.replace('"', '""') + '"'


def _value(value):
    return {'base64': base64.b64encode(value).decode('ascii')} if isinstance(value, bytes) else value


def snapshot(database):
    result = {}
    with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
        for (table,) in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"):
            if table in EXCLUDED:
                continue
            info = db.execute('pragma table_info(' + _identifier(table) + ')').fetchall()
            columns = [row[1] for row in info if not (table == 'auth_user' and row[1] == 'last_login')]
            primary = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
            if not primary:
                raise ValueError('Retained application tables must have stable primary keys.')
            query = 'select ' + ','.join(map(_identifier, columns)) + ' from ' + _identifier(table)
            query += ' order by ' + ','.join(map(_identifier, primary))
            result[table] = {'columns': columns, 'primary': primary,
                             'rows': [[_value(value) for value in row] for row in db.execute(query)]}
    return result


def _support_metadata_additions(before, after, database):
    """Allow only exact default metadata for reviewed, newly added empty tables.

    Existing rows and grants stay immutable. Both the table schema and applied
    migration must prove each allowance; unknown metadata still rejects recovery.
    """
    if not {'django_content_type', 'auth_permission'} <= set(before) & set(after):
        return {}
    groups = [
        ({'0057_server_update_requests', '0058_support_cases'}, {
            'supportcase': ('core_supportcase', 'support case', {
                'id', 'request_key', 'request_digest', 'category', 'description',
                'source_release', 'report', 'report_digest', 'created_at',
                'company_id', 'created_by_id', 'project_id'}),
            'supportevent': ('core_supportevent', 'support event', {
                'id', 'sequence', 'request_key', 'input_digest', 'kind', 'status',
                'details', 'created_at', 'actor_id', 'case_id'}),
        }),
        ({'0059_task_page_indexes', '0060_invitation_email_delivery'}, {
            'invitationemaildelivery': ('core_invitationemaildelivery', 'invitation email delivery', {
                'id', 'invitation_id', 'status', 'attempts', 'available_at', 'lease_id',
                'lease_expires_at', 'error_code', 'accepted_at', 'created_at', 'updated_at'}),
        }),
        ({'0060_invitation_email_delivery', '0061_workflow_email_delivery'}, {
            'workflowemaildelivery': ('core_workflowemaildelivery', 'workflow email delivery', {
                'id', 'dedupe_key', 'event_key', 'kind', 'project_id', 'company_id',
                'checklist_id', 'assignment_id', 'recipient_id', 'expected_role', 'source_audit_id',
                'source_processing_event_id', 'drawing_set_id', 'digest_day',
                'status', 'attempts', 'available_at', 'lease_id', 'lease_expires_at',
                'error_code', 'accepted_at', 'created_at', 'updated_at'}),
        }),
        ({'0061_workflow_email_delivery', '0062_release_notice_acknowledgement'}, {
            'releasenoticeacknowledgement': ('core_releasenoticeacknowledgement', 'release notice acknowledgement', {
                'id', 'user_id', 'release_key', 'acknowledged_at'}),
        }),
    ]
    models = {}
    required_migrations = set()
    for migrations, definitions in groups:
        if any(table in before for table, _, _ in definitions.values()):
            continue
        if not all(table in after for table, _, _ in definitions.values()):
            continue
        for model, (table, label, columns) in definitions.items():
            value = after[table]
            if value['primary'] != ['id'] or set(value['columns']) != columns or value['rows']:
                return {}
            models[model] = label
        required_migrations.update(migrations)
    if not models:
        return {}
    expected_columns = {'django_content_type': {'id', 'app_label', 'model'},
                        'auth_permission': {'id', 'name', 'content_type_id', 'codename'}}
    for table, columns in expected_columns.items():
        if set(before[table]['columns']) != columns or set(after[table]['columns']) != columns:
            return {}
        if before[table]['primary'] != ['id'] or after[table]['primary'] != ['id']:
            return {}
    def named_rows(value):
        return [dict(zip(value['columns'], row)) for row in value['rows']]
    old_types = named_rows(before['django_content_type'])
    if any(row['app_label'] == 'core' and row['model'] in models for row in old_types):
        return {}
    old_ids = {row['id'] for row in old_types}
    types = [row for row in named_rows(after['django_content_type']) if row['id'] not in old_ids]
    if len(types) != len(models) or {(row['app_label'], row['model']) for row in types} != {('core', name) for name in models}:
        return {}
    if any(type(row['id']) is not int or row['id'] <= 0 for row in types):
        return {}
    old_permission_ids = {row['id'] for row in named_rows(before['auth_permission'])}
    permissions = [row for row in named_rows(after['auth_permission']) if row['id'] not in old_permission_ids]
    if any(type(row['id']) is not int or row['id'] <= 0 for row in permissions):
        return {}
    expected_permissions = {(f"Can {action} {models[row['model']]}", row['id'], f"{action}_{row['model']}")
                            for row in types for action in ('add', 'change', 'delete', 'view')}
    if len(permissions) != 4 * len(models) or {(row['name'], row['content_type_id'], row['codename']) for row in permissions} != expected_permissions:
        return {}
    try:
        with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
            placeholders = ','.join('?' for _ in required_migrations)
            applied = {row[0] for row in db.execute(
                "select name from django_migrations where app='core' and name in (" + placeholders + ")",
                sorted(required_migrations))}
    except sqlite3.Error:
        return {}
    if applied != required_migrations:
        return {}
    return {'django_content_type': len(models), 'auth_permission': 4 * len(models)}


def _validate_new_notice_table(before, after, database):
    """Prove the reviewed notice addition even when metadata row deltas are zero.

    An invalid allowance is not evidence of 'no additions'. Existing notice
    tables still use the ordinary strict old-schema/row checks below. Older
    supported upgrades without any notice table/metadata/migration are unchanged.
    """
    table = 'core_releasenoticeacknowledgement'
    model = 'releasenoticeacknowledgement'
    if table in before:
        return
    types = after.get('django_content_type', {})
    type_columns = types.get('columns', [])
    type_rows = [dict(zip(type_columns, row)) for row in types.get('rows', [])]
    notice_types = [row for row in type_rows if row.get('app_label') == 'core' and row.get('model') == model]
    required = {'0061_workflow_email_delivery', '0062_release_notice_acknowledgement'}
    try:
        with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
            applied = {row[0] for row in db.execute(
                "select name from django_migrations where app='core' and name in (?,?)", sorted(required))}
    except sqlite3.Error:
        if table in after or notice_types:
            raise ValueError('New release notice migration evidence is unavailable.') from None
        return
    if table not in after and not notice_types and '0062_release_notice_acknowledgement' not in applied:
        return
    value = after.get(table)
    if (not value or value['primary'] != ['id'] or value['rows']
            or set(value['columns']) != {'id', 'user_id', 'release_key', 'acknowledged_at'}
            or applied != required):
        raise ValueError('New release notice table or migration is not the reviewed empty addition.')
    metadata_columns = {'django_content_type': {'id', 'app_label', 'model'},
                        'auth_permission': {'id', 'name', 'content_type_id', 'codename'}}
    for name, columns in metadata_columns.items():
        if (name not in before or name not in after or before[name]['primary'] != ['id']
                or after[name]['primary'] != ['id'] or set(before[name]['columns']) != columns
                or set(after[name]['columns']) != columns):
            raise ValueError('New release notice metadata cannot be verified.')
    if len(notice_types) != 1 or type(notice_types[0].get('id')) is not int or notice_types[0]['id'] <= 0:
        raise ValueError('New release notice content type is missing or invalid.')
    type_id = notice_types[0]['id']
    permission_rows = [dict(zip(after['auth_permission']['columns'], row)) for row in after['auth_permission']['rows']]
    permissions = [row for row in permission_rows if row['content_type_id'] == type_id]
    expected = {(f'Can {action} release notice acknowledgement', f'{action}_{model}')
                for action in ('add', 'change', 'delete', 'view')}
    if (len(permissions) != 4 or any(type(row['id']) is not int or row['id'] <= 0 for row in permissions)
            or {(row['name'], row['codename']) for row in permissions} != expected):
        raise ValueError('New release notice default permissions are missing or invalid.')


def assert_retained(before, database):
    after = snapshot(database)
    _validate_new_notice_table(before, after, database)
    metadata_additions = _support_metadata_additions(before, after, database)
    for table, original in before.items():
        current = after.get(table)
        if not current or current['primary'] != original['primary'] or current['columns'] != original['columns']:
            raise ValueError('Retained application schema changed unexpectedly.')
        indices = [original['columns'].index(key) for key in original['primary']]
        def identity(row):
            return json.dumps([row[index] for index in indices], sort_keys=True, separators=(',', ':'))
        retained = {identity(row): row for row in current['rows']}
        if any(retained.get(identity(row)) != row for row in original['rows']):
            raise ValueError('An existing application row was removed or changed during upgrade/recovery.')
        if table != 'core_governanceaudit' and len(current['rows']) != len(original['rows']) + metadata_additions.get(table, 0):
            raise ValueError('An unrelated application table gained rows during maintenance.')
    canonical = json.dumps(before, sort_keys=True, separators=(',', ':')).encode()
    return {'retained_tables': len(before), 'retained_rows': sum(len(value['rows']) for value in before.values()),
            'retained_rows_sha256': hashlib.sha256(canonical).hexdigest(),
            'excluded_maintenance_tables': sorted(EXCLUDED),
            'allowed_authentication_change': 'auth_user.last_login', 'audit_policy': 'existing rows identical; append allowed'}


def seed(*, engineer_password=None):
    if os.environ.get('ISURVIX_DISPOSABLE_REHEARSAL') != 'yes':
        raise ValueError('Synthetic seeding requires the explicit disposable rehearsal environment.')
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from django.utils import timezone
    from io import BytesIO
    from types import SimpleNamespace
    from PIL import Image
    from reportlab.pdfgen import canvas
    from core.models import Company, ChecklistTemplate, Project, Checklist, Profile, PhotoEvidence, PhotoPlacement, GovernanceAudit
    from core.survey_processing_models import SurveyDocument
    from core import survey_processing
    users = get_user_model()
    if users.objects.count() != 1 or not users.objects.filter(username='synthetic_owner', is_superuser=True).exists() or Company.objects.exists() or Checklist.objects.exists():
        raise ValueError('Seed only the pristine synthetic customer rehearsal; existing operational data is refused.')
    company = Company.objects.create(name='SYNTHETIC upgrade retention company')
    definition = {'title': 'SYNTHETIC retained template', 'sections': [{'id': 'civil', 'title': 'Civil', 'fields': [
        {'id': 'civil_photo', 'label': 'Synthetic foundation evidence', 'type': 'photo', 'required': False},
        {'id': 'notes', 'label': 'Retained human remarks', 'type': 'text'}]}]}
    template = ChecklistTemplate.objects.create(name='SYNTHETIC upgrade template', definition=definition, published=True, checklist_required=True,
                                                client_left_name='', client_right_name='')
    project = Project.objects.create(name='SYNTHETIC upgrade project', company=company, checklist_template=template)
    engineer = users.objects.create_user('synthetic_retained_engineer', password=engineer_password)
    engineer.profile.company = company
    engineer.profile.project = project
    engineer.profile.role = Profile.Roles.ENGINEER
    engineer.profile.save()
    checklist = Checklist.objects.create(project=project, user=engineer, site_id='SYNTHETIC-UPDATE-001',
                                          answer_data={'custom': {'notes': 'Human fixture remark: retain exactly.'}})
    photos = []
    for number, color in enumerate(('blue', 'green', 'red'), 1):
        buffer = BytesIO()
        Image.new('RGB', (80, 60), color).save(buffer, 'PNG')
        raw = buffer.getvalue()
        photo = PhotoEvidence.objects.create(checklist=checklist, uploaded_by=engineer, group='Civil',
                                              filename=f'synthetic-original-{number}.png', sha256=hashlib.sha256(raw).hexdigest())
        photo.original.save(photo.filename, ContentFile(raw))
        photo.preview.save(photo.filename, ContentFile(raw))
        photos.append(photo)
    PhotoPlacement.objects.create(photo=photos[0], field_id='civil_photo', section_id='civil', status='manual',
                                  schema_digest=hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest(),
                                  reviewed_by=users.objects.get(username='synthetic_owner'), reviewed_at=timezone.now(),
                                  reason='Synthetic retained assignment, not engineering acceptance.')
    document = BytesIO()
    pdf = canvas.Canvas(document)
    pdf.drawString(40, 800, 'SYNTHETIC upgrade evidence: original bytes must survive.')
    pdf.save()
    raw = document.getvalue()
    report = SurveyDocument(checklist=checklist, uploaded_by=engineer, filename='synthetic-retained-report.pdf',
                            sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), content_type='application/pdf')
    report.original.save(report.filename, ContentFile(raw), save=True)
    revision, created = survey_processing.submit(SimpleNamespace(user=engineer), checklist.pk, True)
    if not created or revision.processing_job.status != 'queued':
        raise ValueError('The actual synthetic survey did not retain a queued processing revision.')
    GovernanceAudit.objects.create(action='synthetic_upgrade_retention', actor=engineer, actor_name=engineer.username,
                                   details={'synthetic_only': True, 'checklist_id': checklist.pk, 'engineering_approval': False})
    return {'synthetic_only': True, 'surveys': 1, 'original_photos': 3, 'photo_previews': 3, 'documents': 1,
            'manual_assignments': 1, 'processing_revisions': 1, 'queued_jobs': 1, 'native_ai_calls': 0,
            'first_photo': {'checklist_id': checklist.pk, 'photo_id': photos[0].pk, 'sha256': photos[0].sha256},
            'engineering_approvals_created': 0}
