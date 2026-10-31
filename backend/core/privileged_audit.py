"""Allowlisted, persisted authority snapshots for existing governance events.

This module does not authorize an operation or write a second event. Callers
retain their guards and insert one GovernanceAudit in the same transaction as
the privileged change. Database administrator access is a separate trust boundary.
"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import router

from .models import ClientOrganization, Profile, Project, ProjectInvitation, ProjectMembership


_USER = {'id', 'role', 'company_id', 'project_id', 'admin_industry_id', 'admin_industry_pending',
         'is_active', 'is_staff', 'is_superuser', 'is_locked', 'failed_attempts', 'login_locked_until'}
_PROJECT = {'id', 'company_id', 'administrator_id', 'client_organization_id', 'industry',
            'checklist_template_id', 'review_layers', 'name'}
_MEMBERSHIP = {'id', 'exists', 'user_id', 'project_id', 'company_id', 'user_company_id',
               'primary_project_id', 'role', 'is_active', 'is_primary', 'expires_at'}
_INVITATION = {'id', 'company_id', 'project_id', 'admin_industry_id', 'role', 'created_by_id',
               'accepted_by_id', 'expires_at', 'accepted_at', 'revoked_at'}
_CLIENT = {'id', 'name', 'company_id', 'industry_id', 'created_by_id'}
_MAINTENANCE = {'sessions', 'locked_profiles', 'open_invitations'}
_FIELDS = {'user': _USER, 'project': _PROJECT, 'membership': _MEMBERSHIP,
           'invitation': _INVITATION, 'client_organization': _CLIENT, 'maintenance': _MAINTENANCE}
_BOOLEANS = {'admin_industry_pending', 'is_active', 'is_staff', 'is_superuser', 'is_locked', 'exists', 'is_primary'}
_COUNTS = {'failed_attempts', *_MAINTENANCE}
_TIMESTAMPS = {'expires_at', 'accepted_at', 'revoked_at', 'login_locked_until'}
_ROLES = {str(choice[0]) for choice in Profile.Roles.choices}


def _database(obj):
    return getattr(getattr(obj, '_state', None), 'db', None) or router.db_for_read(type(obj), instance=obj)


def _id(obj):
    value = getattr(obj, 'pk', None)
    if type(value) is not int or value <= 0:
        raise ValidationError('A saved record is required for a privileged audit snapshot.')
    return value


def _iso(value):
    return value.isoformat() if value is not None else None


def _one(model, obj, fields):
    record = model.objects.using(_database(obj)).filter(pk=_id(obj)).values(*fields).first()
    if record is None:
        raise ValidationError('The audit subject no longer exists.')
    return record


def snapshot_user(user):
    row = _one(get_user_model(), user, ['id', 'is_active', 'is_staff', 'is_superuser',
        'profile__role', 'profile__company_id', 'profile__project_id', 'profile__project__company_id',
        'profile__admin_industry_id', 'profile__admin_industry_pending', 'profile__is_locked',
        'profile__failed_attempts', 'profile__login_locked_until'])
    return {'id': row['id'], 'role': row['profile__role'],
            'company_id': row['profile__company_id'] or row['profile__project__company_id'],
            'project_id': row['profile__project_id'], 'admin_industry_id': row['profile__admin_industry_id'],
            'admin_industry_pending': row['profile__admin_industry_pending'],
            'is_active': row['is_active'], 'is_staff': row['is_staff'], 'is_superuser': row['is_superuser'],
            'is_locked': row['profile__is_locked'], 'failed_attempts': row['profile__failed_attempts'],
            'login_locked_until': _iso(row['profile__login_locked_until'])}


def snapshot_project(project):
    return _one(Project, project, sorted(_PROJECT))


def snapshot_membership(user, project):
    alias = _database(project)
    if _database(user) != alias:
        raise ValidationError('Audit subjects must belong to the same database.')
    principal = snapshot_user(user)
    current_project = snapshot_project(project)
    row = ProjectMembership.objects.using(alias).filter(user_id=_id(user), project_id=_id(project)).values(
        'id', 'is_active', 'is_primary', 'expires_at').first()
    return {'id': row['id'] if row else None, 'exists': row is not None,
            'user_id': principal['id'], 'project_id': current_project['id'],
            'company_id': current_project['company_id'], 'user_company_id': principal['company_id'],
            'primary_project_id': principal['project_id'], 'role': principal['role'],
            'is_active': row['is_active'] if row else False,
            'is_primary': row['is_primary'] if row else False,
            'expires_at': _iso(row['expires_at']) if row else None}


def snapshot_invitation(invitation):
    row = _one(ProjectInvitation, invitation, sorted(_INVITATION))
    for field in _TIMESTAMPS & row.keys():
        row[field] = _iso(row[field])
    return row


def snapshot_client_organization(organization):
    return _one(ClientOrganization, organization, sorted(_CLIENT))


def snapshot_maintenance(using='default'):
    return {'sessions': Session.objects.using(using).count(),
            'locked_profiles': Profile.objects.using(using).filter(is_locked=True).count(),
            'open_invitations': ProjectInvitation.objects.using(using).filter(
                accepted_at__isnull=True, revoked_at__isnull=True).count()}


def _clean(kind, value):
    if value is None:
        return None
    if not isinstance(value, dict) or not set(value) <= _FIELDS[kind]:
        raise ValidationError('Only allowlisted privilege snapshot fields may be audited.')
    result = {}
    for field, item in value.items():
        if field in _BOOLEANS:
            valid = item is None or type(item) is bool
        elif field == 'role':
            valid = item is None or (isinstance(item, str) and item in _ROLES)
        elif field in _COUNTS:
            valid = item is None or (type(item) is int and item >= 0)
        elif field in _TIMESTAMPS:
            valid = item is None
            if isinstance(item, str):
                try:
                    datetime.fromisoformat(item)
                    valid = True
                except ValueError:
                    valid = False
        elif field in {'name', 'industry'}:
            valid = isinstance(item, str) and len(item) <= (160 if field == 'name' else 20)
        elif field == 'review_layers':
            valid = item is None or (type(item) is int and item in {3, 4})
        else:
            valid = item is None or (type(item) is int and item > 0)
        if not valid:
            raise ValidationError('A privilege snapshot contains an invalid typed value.')
        result[field] = item
    return result


def change_details(actor, target_kind, target_id, before, after, project=None, company_id=None):
    """Return a detached safe envelope for one existing audit insertion.

    Existing action and legacy details remain the caller's responsibility. None
    before/after denotes creation/removal. A missing membership is instead a
    snapshot with exists=False so legacy primary affiliation remains visible.
    """
    if target_kind not in _FIELDS:
        raise ValidationError('Choose a supported privileged audit subject.')
    if target_id is not None and (type(target_id) is not int or target_id <= 0):
        raise ValidationError('A valid privileged audit subject ID is required.')
    old = _clean(target_kind, before)
    new = _clean(target_kind, after)
    principal = _clean('user', snapshot_user(actor))
    project_state = snapshot_project(project) if project is not None else None
    if project is not None and _database(actor) != _database(project):
        raise ValidationError('Audit scope must belong to the actor database.')
    if company_id is not None and (type(company_id) is not int or company_id <= 0):
        raise ValidationError('A valid audit company scope is required.')
    if project_state and company_id is not None and company_id != project_state['company_id']:
        raise ValidationError('Audit company and project scope do not agree.')
    subject = new or old or {}
    scope_company = project_state['company_id'] if project_state else company_id
    if scope_company is None:
        scope_company = subject.get('company_id', principal['company_id'])
    scope_project = project_state['id'] if project_state else subject.get('project_id')
    return {'privileged_change': {'version': 1, 'actor': principal,
            'target': {'kind': target_kind, 'id': target_id},
            'scope': {'company_id': scope_company, 'project_id': scope_project},
            'before': old, 'after': new}}
