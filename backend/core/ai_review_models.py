"""Private-by-default checklist critique, separate from survey/export content."""
from django.conf import settings
from django.db import models

class ChecklistAIReview(models.Model):
    checklist = models.ForeignKey('core.Checklist', on_delete=models.CASCADE, related_name='ai_reviews')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    model = models.CharField(max_length=160)
    snapshot_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default='running')
    findings = models.JSONField(default=list)
    error = models.CharField(max_length=240, blank=True)
    shared = models.BooleanField(default=False)
    shared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    shared_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
