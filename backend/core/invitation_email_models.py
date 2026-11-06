"""One durable delivery per invitation; bearer links never stored in this table."""
import uuid
from django.db import models
from django.utils import timezone


class InvitationEmailDelivery(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENDING = 'sending', 'Sending'
        ACCEPTED = 'accepted', 'Accepted by Microsoft 365'
        FAILED = 'failed', 'Failed'
        UNCERTAIN = 'uncertain', 'Send outcome uncertain'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.OneToOneField('core.ProjectInvitation', on_delete=models.CASCADE,
                                    related_name='email_delivery')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    lease_id = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['status', 'available_at'], name='invite_mail_ready_idx')]
