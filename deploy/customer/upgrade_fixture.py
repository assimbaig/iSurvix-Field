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


def assert_retained(before, database):
    after = snapshot(database)
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
        if table != 'core_governanceaudit' and len(current['rows']) != len(original['rows']):
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
