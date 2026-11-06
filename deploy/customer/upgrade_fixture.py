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
import re
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
    groups.append(({'0063_checklist_template_company_scope','0064_company_notification_settings'}, {
        'companynotificationsettings': ('core_companynotificationsettings','company notification settings', {
            'id','version','templates','combined_daily_enabled','daily_time','timezone_name','digest_started_at','last_digest_day','last_digest_end','updated_at','company_id','updated_by_id'}),
    }))
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


def _validate_new_notification_settings(before,after,database,source_database=None):
    table='core_companynotificationsettings';model='companynotificationsettings'
    if table in before:return
    types=after.get('django_content_type',{})
    type_rows=[dict(zip(types.get('columns',[]),row)) for row in types.get('rows',[])]
    candidates=[row for row in type_rows if row.get('app_label')=='core' and row.get('model')==model]
    with closing(sqlite3.connect(Path(database).absolute().as_uri()+'?mode=ro',uri=True)) as db:
        try:
            applied=db.execute("select 1 from django_migrations where app='core' and name='0064_company_notification_settings'").fetchone()
        except sqlite3.Error:
            if table in after or candidates:raise ValueError('Notification settings migration evidence is unavailable.') from None
            return
        if table not in after and not candidates and not applied:return
        if table not in after and candidates and not applied:
            # Backward migration fixtures retain ContentType/Permission rows.
            # Treat them as old retained records only with both source and
            # target proving that0064 itself is absent, and exact same rows.
            def named_rows(snapshot,name):
                value=snapshot.get(name,{})
                return [dict(zip(value.get('columns',[]),row)) for row in value.get('rows',[])]
            old_candidates=[row for row in named_rows(before,'django_content_type') if row.get('app_label')=='core' and row.get('model')==model]
            def permission_rows(snapshot,type_ids):
                return [row for row in named_rows(snapshot,'auth_permission') if row.get('content_type_id') in type_ids]
            if source_database is None or candidates!=old_candidates or permission_rows(before,{row['id'] for row in old_candidates})!=permission_rows(after,{row['id'] for row in candidates}):
                raise ValueError('Preexisting notification metadata cannot be verified as unchanged legacy records.')
            try:
                with closing(sqlite3.connect(Path(source_database).absolute().as_uri()+'?mode=ro',uri=True)) as source:
                    source_applied=source.execute("select 1 from django_migrations where app='core' and name='0064_company_notification_settings'").fetchone()
                    source_table=source.execute("select 1 from sqlite_master where type='table' and name=?",(table,)).fetchone()
            except sqlite3.Error:raise ValueError('Source notification migration evidence is unavailable.') from None
            if source_applied or source_table:raise ValueError('Source notification table and migration state are inconsistent.')
            return
        value=after.get(table)
        expected=[('id','integer',1,None,1),('version','integer unsigned',1,None,0),('templates','text',1,None,0),
            ('combined_daily_enabled','bool',1,None,0),('daily_time','time',1,None,0),('timezone_name','varchar(80)',1,None,0),
            ('digest_started_at','datetime',0,None,0),('last_digest_day','date',0,None,0),('last_digest_end','datetime',0,None,0),('updated_at','datetime',1,None,0),('company_id','bigint',1,None,0),('updated_by_id','integer',0,None,0)]
        info=[(row[1],row[2].lower(),row[3],row[4],row[5]) for row in db.execute('pragma table_info('+_identifier(table)+')')]
        fks={tuple(row[2:]) for row in db.execute('pragma foreign_key_list('+_identifier(table)+')')}
        required_fks={('auth_user','updated_by_id','id','NO ACTION','NO ACTION','NONE'),('core_company','company_id','id','NO ACTION','NO ACTION','NONE')}
        table_sql=db.execute("select sql from sqlite_master where type='table' and name=?",(table,)).fetchone()
    # This is an unreleased CreateModel-only addition. Its whole reviewed SQL
    # contract matters: presence checks alone admit extra restrictive CHECKs,
    # hidden defaults, changed deferrability, or other unreviewed constraints.
    expected_sql='CREATE TABLE "core_companynotificationsettings" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "version" integer unsigned NOT NULL CHECK ("version" >= 0), "templates" text NOT NULL CHECK ((JSON_VALID("templates") OR "templates" IS NULL)), "combined_daily_enabled" bool NOT NULL, "daily_time" time NOT NULL, "timezone_name" varchar(80) NOT NULL, "digest_started_at" datetime NULL, "last_digest_day" date NULL, "last_digest_end" datetime NULL, "updated_at" datetime NOT NULL, "company_id" bigint NOT NULL UNIQUE REFERENCES "core_company" ("id") DEFERRABLE INITIALLY DEFERRED, "updated_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED)'
    canonical=lambda value:re.sub(r'\s+',' ',value).strip().upper()
    if not table_sql or canonical(table_sql[0])!=canonical(expected_sql):
        raise ValueError('Notification settings table constraints differ from the reviewed exact contract.')
    if (not applied or not value or value['primary']!=['id'] or value['rows'] or info!=expected or fks!=required_fks
        or not table_sql or 'JSON_VALID' not in table_sql[0].upper()
        or not re.search(r'CHECK\s*\(\s*"version"\s*>=\s*0\s*\)',table_sql[0],re.I)):
        raise ValueError('Notification settings schema/migration is not the reviewed empty addition.')
    indices=_application_indexes(database,table)
    if (len(indices)!=2 or not any(index['unique'] and index['origin']=='u' and not index['partial'] and index['columns']==[('company_id',False)] for index in indices)
        or not any(not index['unique'] and index['origin']=='c' and not index['partial'] and index['columns']==[('updated_by_id',False)] for index in indices)):
        raise ValueError('Notification settings indexes are not the reviewed company/user constraints.')
    if len(candidates)!=1 or type(candidates[0].get('id')) is not int or candidates[0]['id']<=0:raise ValueError('Notification settings content type is missing or invalid.')
    permissions=after.get('auth_permission',{})
    rows=[dict(zip(permissions.get('columns',[]),row)) for row in permissions.get('rows',[])]
    rows=[row for row in rows if row.get('content_type_id')==candidates[0]['id']]
    expected_permissions={(f'Can {action} company notification settings',f'{action}_{model}') for action in ('add','change','delete','view')}
    if (len(rows)!=4 or any(type(row.get('id')) is not int or row['id']<=0 for row in rows)
        or {(row.get('name'),row.get('codename')) for row in rows}!=expected_permissions):
        raise ValueError('Notification settings default permission metadata is missing or invalid.')
    return True


def _validate_checklist_template_company_scope(before, after, database):
    """Allow only migration 0063's additive owner field and deterministic backfill."""
    table = 'core_checklisttemplate'
    previous = before.get(table)
    current = after.get(table)
    try:
        with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
            applied = db.execute(
                "select 1 from django_migrations where app='core' and name=?",
                ('0063_checklist_template_company_scope',)).fetchone()
    except sqlite3.Error:
        if not previous or not current or 'company_id' not in current['columns']:
            return None
        raise ValueError('Checklist template company scope migration evidence is unavailable.') from None
    if applied and (not previous or not current or 'company_id' not in current['columns']):
        raise ValueError('Migration 0063 is recorded but the checklist template company column is missing.')
    if (not previous or not current or 'company_id' in previous['columns']
            or 'company_id' not in current['columns']):
        return None
    if current['columns'] != previous['columns'] + ['company_id'] or current['primary'] != previous['primary']:
        raise ValueError('Checklist template schema changed beyond the approved company scope field.')
    try:
        with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
            template_info = db.execute('pragma table_info(' + _identifier(table) + ')').fetchall()
            company_info = db.execute('pragma table_info("core_company")').fetchall()
            foreign_keys = db.execute('pragma foreign_key_list(' + _identifier(table) + ')').fetchall()
    except sqlite3.Error:
        raise ValueError('Checklist template company scope migration evidence is unavailable.') from None
    column = next((row for row in template_info if row[1] == 'company_id'), None)
    company_pk = next((row for row in company_info if row[1] == 'id' and row[5] == 1), None)
    company_foreign_keys = [row for row in foreign_keys if row[3] == 'company_id']
    if (not applied or not column or not company_pk or column[2].lower() != 'bigint'
            or column[3] != 0 or column[4] is not None or len(company_foreign_keys) != 1
            or tuple(company_foreign_keys[0][2:]) != ('core_company', 'company_id', 'id',
                                                       'NO ACTION', 'NO ACTION', 'NONE')):
        raise ValueError('Checklist template company scope migration or foreign key is unverified.')

    def rows_by_id(value):
        columns = value['columns']
        if columns.count('id') != 1:
            raise ValueError('Checklist template rows do not have stable identities.')
        return {row[columns.index('id')]: dict(zip(columns, row)) for row in value['rows']}

    old_templates = rows_by_id(previous)
    new_templates = rows_by_id(current)
    if set(old_templates) != set(new_templates):
        raise ValueError('Checklist template records changed during the company scope migration.')
    expected_companies = {template_id: set() for template_id in old_templates}

    def table_rows(name):
        value = before.get(name)
        if not value:
            raise ValueError('Company scope ownership references are unavailable.')
        return [dict(zip(value['columns'], row)) for row in value['rows']]

    projects = table_rows('core_project')
    project_by_id = {row['id']: row for row in projects}
    for project in projects:
        template_id = project.get('checklist_template_id')
        company_id = project.get('company_id')
        if template_id in expected_companies and company_id is not None:
            expected_companies[template_id].add(company_id)
    for checklist in table_rows('core_checklist'):
        template_id = checklist.get('checklist_template_id')
        project = project_by_id.get(checklist.get('project_id'))
        if template_id in expected_companies and project and project.get('company_id') is not None:
            expected_companies[template_id].add(project['company_id'])

    assigned = 0
    for template_id, original in old_templates.items():
        definition = original.get('definition')
        if isinstance(definition, str):
            try:
                definition = json.loads(definition)
            except (TypeError, ValueError):
                definition = {}
        expected = None
        if not (isinstance(definition, dict) and definition.get('standard_catalog')):
            owners = expected_companies[template_id]
            if len(owners) == 1:
                expected = next(iter(owners))
                assigned += 1
        updated = new_templates[template_id]
        if any(updated.get(column) != value for column, value in original.items()):
            raise ValueError('Existing checklist template data changed during the company scope migration.')
        if updated.get('company_id') != expected:
            raise ValueError('Checklist template company scope does not match unambiguous project ownership.')
    return {'expected_companies': {key: (next(iter(value)) if len(value) == 1 else None)
                                   for key, value in expected_companies.items()},
            'assigned_count': assigned}


def _reject_unreviewed_application_triggers(database):
    """Do not accept hidden SQLite behavior outside the retained row snapshot."""
    try:
        with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
            triggers = db.execute(
                "select name from sqlite_master where type='trigger' and tbl_name not like 'sqlite_%'"
            ).fetchall()
    except sqlite3.Error:
        raise ValueError('SQLite trigger inventory is unavailable for retention verification.') from None
    if triggers:
        raise ValueError('Unreviewed SQLite triggers prevent verified data retention.')


def _application_indexes(database, table):
    with closing(sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True)) as db:
        result = []
        for row in db.execute('pragma index_list(' + _identifier(table) + ')').fetchall():
            name = row[1]
            columns = [(item[2], bool(item[3])) for item in db.execute(
                'pragma index_xinfo(' + _identifier(name) + ')').fetchall() if item[5]]
            result.append({'name': name, 'unique': bool(row[2]), 'origin': row[3],
                           'partial': bool(row[4]), 'columns': columns})
    return result


def _validate_application_indexes(source_database, target_database):
    """Allow only indexes explicitly introduced by the reviewed 0059/0063 migrations."""
    source_tables = set(snapshot(source_database))
    target_tables = set(snapshot(target_database))
    expected_template_name = re.compile(r'^core_checklisttemplate_company_id_[a-f0-9]{8}$')
    expected = {
        ('core_checklist', 'ck_project_updated_page', False, 'c', False,
         (('project_id', False), ('updated_at', True), ('id', False))),
        ('core_workassignment', 'wa_project_task_page', False, 'c', False,
         (('project_id', False), ('checklist_id', False), ('created_at', True), ('id', False))),
    }
    for table in sorted(source_tables & target_tables):
        before = _application_indexes(source_database, table)
        after = _application_indexes(target_database, table)
        removed = [index for index in before if index not in after]
        added = [index for index in after if index not in before]
        if removed:
            raise ValueError('An existing application index was removed during verified upgrade.')
        for index in added:
            signature = (table, index['name'], index['unique'], index['origin'],
                         index['partial'], tuple(index['columns']))
            company_fk = (table == 'core_checklisttemplate'
                          and expected_template_name.fullmatch(index['name'])
                          and not index['unique'] and index['origin'] == 'c'
                          and not index['partial'] and index['columns'] == [('company_id', False)])
            if signature not in expected and not company_fk:
                raise ValueError('Application index changes exceed the reviewed migration allowlist.')


def assert_retained(before, database, *, source_database=None):
    _reject_unreviewed_application_triggers(database)
    after = snapshot(database)
    _validate_new_notice_table(before, after, database)
    notification_settings_added=_validate_new_notification_settings(before,after,database,source_database=source_database)
    company_scope = _validate_checklist_template_company_scope(before, after, database)
    if company_scope is not None or notification_settings_added:
        if source_database is None:
            raise ValueError('Source database is required to verify reviewed migration index changes.')
        _validate_application_indexes(source_database, database)
    metadata_additions = _support_metadata_additions(before, after, database)
    for table, original in before.items():
        current = after.get(table)
        allowed_company_scope = table == 'core_checklisttemplate' and company_scope is not None
        if (not current or current['primary'] != original['primary']
                or (current['columns'] != original['columns'] and not allowed_company_scope)):
            raise ValueError('Retained application schema changed unexpectedly.')
        indices = [original['columns'].index(key) for key in original['primary']]
        def identity(row):
            return json.dumps([row[index] for index in indices], sort_keys=True, separators=(',', ':'))
        retained = {identity(row): row for row in current['rows']}
        if allowed_company_scope:
            current_columns = current['columns']
            current_rows = [dict(zip(current_columns, row)) for row in current['rows']]
            for row in current_rows:
                row.pop('company_id', None)
            normalized = [[row[column] for column in original['columns']] for row in current_rows]
            current_ids = {row[original['columns'].index('id')] for row in normalized}
            old_ids = {row[original['columns'].index('id')] for row in original['rows']}
            if current_ids != old_ids or normalized != original['rows']:
                raise ValueError('Existing checklist template data changed during the company scope migration.')
        elif any(retained.get(identity(row)) != row for row in original['rows']):
            raise ValueError('An existing application row was removed or changed during upgrade/recovery.')
        if table != 'core_governanceaudit' and len(current['rows']) != len(original['rows']) + metadata_additions.get(table, 0):
            raise ValueError('An unrelated application table gained rows during maintenance.')
    canonical = json.dumps(before, sort_keys=True, separators=(',', ':')).encode()
    result = {'retained_tables': len(before), 'retained_rows': sum(len(value['rows']) for value in before.values()),
            'retained_rows_sha256': hashlib.sha256(canonical).hexdigest(),
            'excluded_maintenance_tables': sorted(EXCLUDED),
            'allowed_authentication_change': 'auth_user.last_login', 'audit_policy': 'existing rows identical; append allowed'}
    if company_scope is not None:
        result['company_scoped_templates'] = company_scope['assigned_count']
    return result


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
