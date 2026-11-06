"""Invitation outbox. Network requests run outside short database transactions.

New queued links are derived with a dedicated HMAC purpose from a random UUID.
The database stores that nonce and the usual token hash, never the bearer token.
Old random/manual invitation links remain valid and are never reconstructed.
Ambiguous Graph POST outcomes require operator investigation, not automatic resend.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import GovernanceAudit, InvitationEmailDelivery
from .notification_email import GraphMailClient, NotificationEmailError

MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


def _token(delivery_id, key=None):
    return salted_hmac('core.invitation-email.v1', str(delivery_id),
                       secret=settings.SECRET_KEY if key is None else key, algorithm='sha256').hexdigest()


def prepare_invitation_token():
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', False):
        return secrets.token_urlsafe(32), None
    delivery_id = uuid.uuid4()
    return _token(delivery_id), delivery_id


def _audit(delivery, action):
    invitation = delivery.invitation
    GovernanceAudit.objects.create(actor=invitation.created_by, actor_name='',
        project=invitation.project, action='invitation_email.' + action,
        details={'invitation_id': invitation.pk, 'delivery_id': str(delivery.pk),
                 'status': delivery.status, 'attempts': delivery.attempts, 'code': delivery.error_code})


def queue_invitation_email(invitation, delivery_id):
    if delivery_id is None:
        return None
    expected = hashlib.sha256(_token(delivery_id).encode()).hexdigest()
    if not hmac.compare_digest(invitation.token_hash, expected):
        raise ValidationError('Email delivery must reference its original invitation.')
    delivery, created = InvitationEmailDelivery.objects.get_or_create(
        invitation=invitation, defaults={'id': delivery_id})
    if delivery.pk != delivery_id:
        raise ValidationError('An email delivery already exists for this invitation.')
    if created:
        _audit(delivery, 'queued')
    return delivery


def delivery_status(invitation):
    try:
        delivery = invitation.email_delivery
    except InvitationEmailDelivery.DoesNotExist:
        return 'Email sending is not configured for this invitation. Share the private link manually.'
    labels = {
        'sending': 'Sending invitation from ifield.notify@isurvix.com.',
        'accepted': 'Microsoft 365 accepted the email from ifield.notify@isurvix.com; inbox delivery is not confirmed.',
        'failed': 'Email failed. Share the private link manually or ask the platform administrator to retry.',
        'uncertain': 'Email outcome is uncertain. Check Sent Items before issuing another email.',
        'cancelled': 'Email cancelled because this invitation is no longer available.',
    }
    if delivery.status == 'queued':
        configured = bool(getattr(settings, 'NOTIFICATION_EMAIL_CREDENTIALS_FILE', ''))
        return ('Email queued from ifield.notify@isurvix.com. ' +
                ('Awaiting the email worker.' if configured else
                 'Microsoft 365 authorization is missing; share the private link manually if needed.'))
    return labels.get(delivery.status, 'Email status is unavailable.')


def _public_origin():
    value = getattr(settings, 'NOTIFICATION_EMAIL_PUBLIC_ORIGIN', '').strip()
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        raise NotificationEmailError('invalid_public_origin') from None
    allowed = {h.lower() for h in settings.ALLOWED_HOSTS if h and '*' not in h and not h.startswith('.')}
    if (parts.scheme != 'https' or not parts.hostname or parts.hostname.lower() not in allowed
            or parts.username or parts.password or parts.path or parts.query or parts.fragment
            or port is not None and not 1 <= port <= 65535):
        raise NotificationEmailError('invalid_public_origin')
    return value.rstrip('/')


def recover_interrupted_emails():
    count = 0
    with transaction.atomic():
        deliveries = list(InvitationEmailDelivery.objects.select_for_update().select_related('invitation').filter(
            status='sending', lease_expires_at__lte=timezone.now()))
        for delivery in deliveries:
            delivery.status = 'uncertain'
            delivery.error_code = 'worker_interrupted'
            delivery.lease_id = None
            delivery.lease_expires_at = None
            delivery.save(update_fields=['status', 'error_code', 'lease_id', 'lease_expires_at', 'updated_at'])
            _audit(delivery, 'interrupted')
            count += 1
    return count


def retry_failed_emails():
    count = 0
    with transaction.atomic():
        for delivery in InvitationEmailDelivery.objects.select_for_update().select_related('invitation').filter(status='failed'):
            delivery.status, delivery.error_code, delivery.attempts = 'queued', '', 0
            delivery.available_at = timezone.now()
            delivery.save(update_fields=['status', 'error_code', 'attempts', 'available_at', 'updated_at'])
            _audit(delivery, 'retry')
            count += 1
    return count


def _claim():
    now = timezone.now()
    with transaction.atomic():
        delivery = InvitationEmailDelivery.objects.select_for_update().select_related('invitation').filter(
            status='queued', available_at__lte=now, attempts__lt=MAX_ATTEMPTS).first()
        if delivery is None:
            return None
        delivery.status = 'sending'
        delivery.attempts += 1
        delivery.lease_id = uuid.uuid4()
        delivery.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        delivery.save(update_fields=['status', 'attempts', 'lease_id', 'lease_expires_at', 'updated_at'])
        _audit(delivery, 'started')
        return delivery


def _finish(delivery, status, code=''):
    with transaction.atomic():
        current = InvitationEmailDelivery.objects.select_for_update().select_related('invitation').filter(
            pk=delivery.pk, status='sending', lease_id=delivery.lease_id).first()
        if current is None:
            return
        current.status = status
        current.error_code = code
        current.lease_id = None
        current.lease_expires_at = None
        if status == 'accepted':
            current.accepted_at = timezone.now()
        elif status == 'queued':
            current.available_at = timezone.now() + timedelta(seconds=30 * current.attempts)
        current.save(update_fields=['status', 'error_code', 'lease_id', 'lease_expires_at',
                                    'accepted_at', 'available_at', 'updated_at'])
        _audit(current, status)


def process_next_email():
    if not getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', False):
        return False
    recover_interrupted_emails()
    delivery = _claim()
    if delivery is None:
        return False
    try:
        # Honour key rotation fallbacks only if the retained token hash agrees.
        token = next((t for key in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
                      if hmac.compare_digest(hashlib.sha256((t := _token(delivery.pk, key)).encode()).hexdigest(),
                                             delivery.invitation.token_hash)), None)
        if token is None:
            raise NotificationEmailError('invitation_key_changed')
        from .governance_views import invitation_for
        try:
            invitation = invitation_for(token)
        except Http404:
            _finish(delivery, 'cancelled', 'invitation_unavailable')
            return True
        link = _public_origin() + reverse('governance_accept_invite', args=[token])
        company = invitation.company.name if invitation.company_id else 'your project'
        body = (f'You have been invited to iSurvix iField for {company}.\n'
                f'Assigned role: {invitation.get_role_display()}.\n\n'
                f'Create your account using this private, single-use link:\n{link}\n\n'
                f'This invitation expires at {invitation.expires_at:%Y-%m-%d %H:%M UTC}.\n'
                'If you did not expect this invitation, contact the person who invited you.')
        from .custom_notifications import custom_invitation_message
        subject,body=custom_invitation_message(delivery,invitation,'Your iSurvix iField invitation',body,link)
        GraphMailClient().send(invitation.email, subject, body)
    except NotificationEmailError as error:
        status = 'uncertain' if error.uncertain else (
            'queued' if error.retryable and delivery.attempts < MAX_ATTEMPTS else 'failed')
        _finish(delivery, status, error.code)
    except Exception:
        # An unexpected failure may have happened after Microsoft accepted a POST.
        # Persist uncertainty without logging bearer links, credentials or payloads.
        _finish(delivery, 'uncertain', 'unexpected_delivery_failure')
    else:
        _finish(delivery, 'accepted')
    return True
