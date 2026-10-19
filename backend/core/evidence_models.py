"""Append-only evidence assessments and explicitly released project references."""
from django.conf import settings
from django.db import models
from .revision_models import ImmutableRecord


class EvidenceAnalysisRecord(ImmutableRecord):
    cache_key = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey('core.Company', null=True, on_delete=models.PROTECT)
    project = models.ForeignKey('core.Project', on_delete=models.PROTECT)
    checklist = models.ForeignKey('core.Checklist', on_delete=models.PROTECT, related_name='evidence_analyses')
    photo = models.ForeignKey('core.PhotoEvidence', null=True, on_delete=models.PROTECT, related_name='evidence_analyses')
    site_id = models.CharField(max_length=255)
    photo_sha256 = models.CharField(max_length=64)
    schema_digest = models.CharField(max_length=64)
    rules_version = models.CharField(max_length=160)
    model_version = models.CharField(max_length=160)
    tool_version = models.CharField(max_length=160)
    prompt_version = models.CharField(max_length=160)
    payload = models.JSONField(default=dict)
    payload_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class EvidenceRuleRelease(ImmutableRecord):
    project = models.ForeignKey('core.Project', on_delete=models.PROTECT, related_name='evidence_rule_releases')
    version = models.PositiveIntegerField()
    references = models.JSONField(default=list)
    digest = models.CharField(max_length=64)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'version'], name='unique_project_evidence_release')]
        ordering = ['project_id', 'version']


class EvidenceCorrection(ImmutableRecord):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.PROTECT, related_name='evidence_corrections')
    photo = models.ForeignKey('core.PhotoEvidence', on_delete=models.PROTECT)
    field_id = models.CharField(max_length=80)
    action = models.CharField(max_length=16)
    reason = models.TextField(blank=True)
    source = models.JSONField(default=dict)
    captured_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class EvidenceCorrectionDecision(ImmutableRecord):
    correction = models.OneToOneField(EvidenceCorrection, on_delete=models.PROTECT, related_name='peer_decision')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=10)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class EvidenceReviewBinding(ImmutableRecord):
    review = models.OneToOneField('core.ChecklistAIReview', on_delete=models.PROTECT, related_name='evidence_binding')
    analysis = models.ForeignKey(EvidenceAnalysisRecord, on_delete=models.PROTECT, related_name='review_bindings')
    created_at = models.DateTimeField(auto_now_add=True)
