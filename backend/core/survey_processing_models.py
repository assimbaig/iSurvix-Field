"""Additive survey processing: immutable inputs/results and append-only decisions."""
from django.conf import settings
from django.db import models
from .revision_models import ImmutableRecord


class SurveyDocument(ImmutableRecord):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.PROTECT, related_name='survey_documents')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    original = models.FileField(upload_to='survey_processing/documents/')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['checklist', 'sha256'], name='unique_survey_document_bytes')]


class SurveyUploadSession(models.Model):
    token = models.UUIDField(primary_key=True)
    checklist = models.ForeignKey('core.Checklist', on_delete=models.CASCADE, related_name='survey_upload_sessions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    finished_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SurveyProcessingRevision(ImmutableRecord):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.PROTECT, related_name='processing_revisions')
    number = models.PositiveIntegerField()
    digest = models.CharField(max_length=64)
    snapshot = models.JSONField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-number']
        constraints = [
            models.UniqueConstraint(fields=['checklist', 'number'], name='unique_survey_processing_number'),
            models.UniqueConstraint(fields=['checklist', 'digest'], name='unique_survey_processing_snapshot'),
        ]


class SurveyProcessingJob(models.Model):
    revision = models.OneToOneField(SurveyProcessingRevision, on_delete=models.PROTECT, related_name='processing_job')
    status = models.CharField(max_length=32, default='queued')
    model = models.CharField(max_length=160)
    model_digest = models.CharField(max_length=64, blank=True)
    pipeline_version = models.CharField(max_length=32, default='survey-pipeline-1')
    completed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    lease_owner = models.CharField(max_length=64, blank=True)
    lease_until = models.DateTimeField(null=True)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class SurveySourceAnalysis(ImmutableRecord):
    revision = models.ForeignKey(SurveyProcessingRevision, on_delete=models.PROTECT, related_name='source_analyses')
    source_id = models.CharField(max_length=300)
    payload = models.JSONField()
    digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'source_id'], name='unique_survey_source_analysis')]


class SurveyProcessingResult(ImmutableRecord):
    revision = models.OneToOneField(SurveyProcessingRevision, on_delete=models.PROTECT, related_name='processing_result')
    payload = models.JSONField()
    digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class SurveyProcessingEvent(ImmutableRecord):
    revision = models.ForeignKey(SurveyProcessingRevision, on_delete=models.PROTECT, related_name='processing_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=32)
    reason = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class SurveyDrawingSet(ImmutableRecord):
    revision = models.ForeignKey(SurveyProcessingRevision, on_delete=models.PROTECT, related_name='drawing_sets')
    edition = models.PositiveIntegerField()
    released = models.BooleanField(default=False)
    review_digest = models.CharField(max_length=64)
    geometry = models.JSONField()
    manifest = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'edition'], name='unique_survey_drawing_edition')]
