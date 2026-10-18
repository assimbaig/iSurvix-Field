"""Durable local evidence, inference queue and explicitly reviewed proposals."""
from django.conf import settings
from django.db import models

class PhotoEvidence(models.Model):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.CASCADE, related_name='photo_evidence')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    group = models.CharField(max_length=20, blank=True, default='')
    filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    original = models.FileField(upload_to='photo_pilot/originals/')
    preview = models.FileField(upload_to='photo_pilot/previews/')
    metadata = models.JSONField(default=dict)
    analysis_metadata = models.JSONField(default=dict)
    analysis_signature = models.CharField(max_length=64, blank=True, default='')
    advisories = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['checklist', 'sha256'], name='unique_photo_bytes_per_survey')]

class PhotoJob(models.Model):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.CASCADE, related_name='photo_jobs')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    photos = models.ManyToManyField(PhotoEvidence)
    model = models.CharField(max_length=160)
    status = models.CharField(max_length=20, default='queued')
    error = models.TextField(blank=True)
    completed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    processed_photo_ids = models.JSONField(default=list)
    progress = models.JSONField(default=dict)
    baseline = models.JSONField(default=dict)
    schema = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PhotoDraft(models.Model):
    job = models.ForeignKey(PhotoJob, on_delete=models.CASCADE, related_name='drafts')
    photo = models.ForeignKey(PhotoEvidence, on_delete=models.CASCADE, related_name='drafts')
    field_id = models.CharField(max_length=80)
    label = models.TextField()
    value = models.JSONField(null=True)
    reason = models.TextField()
    uncertainty = models.CharField(max_length=100)
    missing_information = models.TextField(blank=True)
    anomalies = models.JSONField(default=list)
    baseline = models.JSONField(null=True)
    baseline_present = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default='pending')
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    accepted_at = models.DateTimeField(null=True)

class PhotoWorkerLease(models.Model):
    key = models.CharField(max_length=32, primary_key=True)
    owner = models.CharField(max_length=64)
    expires_at = models.DateTimeField()

class PhotoPlacement(models.Model):
    """Evidence locations are separate from answers and require human confirmation."""
    photo = models.ForeignKey(PhotoEvidence, on_delete=models.CASCADE, related_name='placements')
    job = models.ForeignKey(PhotoJob, null=True, on_delete=models.SET_NULL, related_name='placements')
    field_id = models.CharField(max_length=80)
    section_id = models.CharField(max_length=80)
    status = models.CharField(max_length=20, default='proposed')
    confidence = models.CharField(max_length=10, default='low')
    reason = models.TextField(blank=True)
    uncertainty = models.CharField(max_length=10, default='high')
    schema_digest = models.CharField(max_length=64)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['photo','field_id'], name='unique_photo_field_placement')]
