"""Frozen support reports and append-only maintenance history, separate from engineering."""
import uuid
from django.conf import settings
from django.db import models
from .revision_models import ImmutableRecord


STATUS_CHOICES = [
    ('reported', 'Reported'), ('repair_requested', 'Awaiting isolated repair'),
    ('tests_passed', 'Operator tests recorded; PR missing'),
    ('pr_ready', 'Tested PR recorded'), ('changes_requested', 'Changes requested'),
    ('repair_approved', 'Repair approved'), ('release_approved', 'Release approved'),
    ('installed', 'Installed release confirmed'), ('cancelled', 'Cancelled'),
]


class SupportCase(ImmutableRecord):
    CATEGORIES = [('processing', 'AI processing'), ('upload', 'Uploads and evidence'),
                  ('review', 'Review workflow'), ('access', 'Access and invitations'),
                  ('installation', 'Installation and updates'), ('other', 'Other application issue')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True)
    request_digest = models.CharField(max_length=64)
    company = models.ForeignKey('core.Company', null=True, blank=True, on_delete=models.PROTECT)
    project = models.ForeignKey('core.Project', null=True, blank=True, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    category = models.CharField(max_length=24, choices=CATEGORIES)
    description = models.TextField(max_length=2000)
    source_release = models.CharField(max_length=40)
    report = models.JSONField()
    report_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['company', 'created_at'], name='support_company_created')]

    @property
    def latest_event(self):
        prefetched = getattr(self, '_prefetched_objects_cache', {}).get('events')
        return max(prefetched, key=lambda item: item.sequence, default=None) if prefetched is not None else self.events.order_by('-sequence').first()

    @property
    def status(self):
        event = self.latest_event
        return event.status if event else 'reported'

    @property
    def status_label(self):
        return dict(STATUS_CHOICES).get(self.status, 'Unknown')

    @property
    def version(self):
        event = self.latest_event
        return event.sequence if event else 0


class SupportEvent(ImmutableRecord):
    case = models.ForeignKey(SupportCase, on_delete=models.PROTECT, related_name='events')
    sequence = models.PositiveIntegerField()
    request_key = models.UUIDField()
    input_digest = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['case', 'sequence'], name='unique_support_event_sequence'),
            models.UniqueConstraint(fields=['case', 'request_key'], name='unique_support_event_request'),
        ]
