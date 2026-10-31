"""Atomic, replay-safe owner-controlled company onboarding using existing invites."""
from datetime import timedelta
import hashlib
import secrets
import unicodedata
import uuid

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .access import is_super_admin
from .governance_views import audit, issue_guard, lock_governance
from .models import Company, CompanyApplication, IndustryCatalog, Profile, ProjectInvitation
from .privileged_audit import change_details, snapshot_invitation


def _name(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).split())


def _lock(actor):
    lock_governance(actor)
    if not is_super_admin(actor):
        raise PermissionDenied('Only the platform owner can review and provision companies.')


def _active_industry(industry):
    current = IndustryCatalog.objects.filter(pk=getattr(industry, 'pk', industry), is_active=True).first()
    if current is None:
        raise ValidationError('Choose an active industry before continuing onboarding.')
    return current


def _application(application_id):
    try:
        return CompanyApplication.objects.select_for_update().select_related('company', 'industry', 'invitation').get(pk=application_id)
    except CompanyApplication.DoesNotExist:
        raise ValidationError('This application is no longer available.')


def _record(actor, action, application, before):
    audit(actor, 'company_application.' + action, application_id=application.pk,
          company_id=application.company_id, industry_id=application.industry_id,
          before_status=before, after_status=application.status,
          invitation_id=application.invitation_id)


@transaction.atomic
def apply_application(actor, *, request_key, name, email, industry):
    _lock(actor)
    try:
        key = uuid.UUID(str(request_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('The application request key is invalid. Reload the form.')
    name = _name(name)
    if not name or len(name) > 160:
        raise ValidationError('Company name must contain 1–160 characters.')
    email = str(email).strip().lower()
    validate_email(email)
    if len(email) > 254:
        raise ValidationError('The Admin email address is too long.')
    industry = _active_industry(industry)
    replay = CompanyApplication.objects.filter(request_key=key).first()
    if replay:
        if (replay.name_key, replay.email, replay.industry_id) != (name.casefold(), email, industry.pk):
            raise ValidationError('This request key already belongs to different application details.')
        return replay
    pending = CompanyApplication.objects.filter(name_key=name.casefold()).exclude(status=CompanyApplication.Status.REJECTED).first()
    if pending:
        if (pending.email, pending.industry_id) != (email, industry.pk):
            raise ValidationError('An application already exists for this company. Review its original details.')
        return pending
    if any(_name(existing).casefold() == name.casefold() for existing in Company.objects.values_list('name', flat=True)):
        raise ValidationError('This company already exists. Manage its existing access instead of claiming it through onboarding.')
    application = CompanyApplication.objects.create(request_key=key, name=name, name_key=name.casefold(),
        email=email, industry=industry, created_by=actor)
    _record(actor, 'applied', application, None)
    return application


@transaction.atomic
def review_application(actor, application_id, *, approve, reason=''):
    _lock(actor)
    application = _application(application_id)
    if type(approve) is not bool:
        raise ValidationError('Choose approve or reject.')
    note = str(reason).strip()
    if len(note) > 4000:
        raise ValidationError('Keep the review note within 4,000 characters.')
    if not approve and not note:
        raise ValidationError('Give a reason when rejecting a company application.')
    next_status = CompanyApplication.Status.REVIEWED if approve else CompanyApplication.Status.REJECTED
    if application.status == next_status:
        return application
    if approve and application.status in {CompanyApplication.Status.PROVISIONED, CompanyApplication.Status.INVITED}:
        return application
    if application.status != CompanyApplication.Status.APPLIED:
        raise ValidationError('Only a new application can be reviewed. Existing provisioning is preserved.')
    _active_industry(application.industry_id)
    before = application.status
    application.status = next_status
    application.review_note = note
    application.reviewed_by = actor
    application.reviewed_at = timezone.now()
    application.save(update_fields=['status', 'review_note', 'reviewed_by', 'reviewed_at'])
    _record(actor, 'reviewed' if approve else 'rejected', application, before)
    return application


@transaction.atomic
def provision_application(actor, application_id):
    _lock(actor)
    application = _application(application_id)
    if application.status in {CompanyApplication.Status.PROVISIONED, CompanyApplication.Status.INVITED}:
        return application
    if application.status != CompanyApplication.Status.REVIEWED:
        raise ValidationError('Review and approve the application before provisioning its company.')
    _active_industry(application.industry_id)
    if any(_name(existing).casefold() == application.name_key for existing in Company.objects.values_list('name', flat=True)):
        raise ValidationError('A company with this name now exists. No existing company will be claimed.')
    application.company = Company.objects.create(name=application.name)
    application.status = CompanyApplication.Status.PROVISIONED
    application.provisioned_at = timezone.now()
    application.save(update_fields=['company', 'status', 'provisioned_at'])
    _record(actor, 'provisioned', application, CompanyApplication.Status.REVIEWED)
    return application


@transaction.atomic
def invite_application(actor, application_id):
    _lock(actor)
    application = _application(application_id)
    if application.status == CompanyApplication.Status.INVITED:
        return application, None
    if application.status != CompanyApplication.Status.PROVISIONED or not application.company_id:
        raise ValidationError('Provision the approved company before issuing its Admin invitation.')
    industry = _active_industry(application.industry_id)
    issue_guard(actor, None, Profile.Roles.ADMIN, application.company, industry)
    if User.objects.filter(email__iexact=application.email).exists():
        raise ValidationError('This email already has an account. Manage its existing access instead.')
    now = timezone.now()
    if ProjectInvitation.objects.filter(email__iexact=application.email, accepted_at__isnull=True,
            revoked_at__isnull=True, expires_at__gt=now).exists():
        raise ValidationError('A current invitation already uses this email. Resolve it in People and invitations first.')
    token = secrets.token_urlsafe(32)
    invitation = ProjectInvitation.objects.create(token_hash=hashlib.sha256(token.encode()).hexdigest(),
        email=application.email, role=Profile.Roles.ADMIN, company=application.company,
        admin_industry=industry, created_by=actor, expires_at=now + timedelta(hours=72))
    audit(actor, 'invitation_created', invitation_id=invitation.pk, email=application.email,
          role=Profile.Roles.ADMIN,
          **change_details(actor, 'invitation', invitation.pk, None, snapshot_invitation(invitation), company_id=application.company_id))
    application.invitation = invitation
    application.status = CompanyApplication.Status.INVITED
    application.invited_at = now
    application.save(update_fields=['invitation', 'status', 'invited_at'])
    _record(actor, 'invited', application, CompanyApplication.Status.PROVISIONED)
    return application, token
