"""Event/recipient scoped notification delivery, separate from engineering state."""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

from .invitation_email_models import InvitationEmailDelivery


class WorkflowEmailDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dedupe_key = models.CharField(max_length=64, unique=True)
    event_key = models.CharField(max_length=180)
    kind = models.CharField(max_length=24)
    project = models.ForeignKey('core.Project', null=True, on_delete=models.SET_NULL)
    company = models.ForeignKey('core.Company', null=True, on_delete=models.SET_NULL)
    checklist = models.ForeignKey('core.Checklist', null=True, blank=True, on_delete=models.SET_NULL)
    assignment = models.ForeignKey('core.WorkAssignment', null=True, blank=True, on_delete=models.SET_NULL)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    expected_role = models.CharField(max_length=20)
    source_audit = models.ForeignKey('core.GovernanceAudit', null=True, blank=True, on_delete=models.SET_NULL)
    source_processing_event = models.ForeignKey('core.SurveyProcessingEvent', null=True, blank=True, on_delete=models.SET_NULL)
    drawing_set = models.ForeignKey('core.SurveyDrawingSet', null=True, blank=True, on_delete=models.SET_NULL)
    digest_day = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=InvitationEmailDelivery.Status.choices, default='queued')
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
        indexes = [models.Index(fields=['status', 'available_at'], name='workflow_mail_ready_idx'),
                   models.Index(fields=['recipient', 'digest_day'], name='workflow_mail_digest_idx')]
