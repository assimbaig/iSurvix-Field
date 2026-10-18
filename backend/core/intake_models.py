"""Auditable previews for atomic site-assignment intake."""
from django.conf import settings
from django.db import models
class AssignmentIntakeBatch(models.Model):
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    source_filename=models.CharField(max_length=255)
    source_sha256=models.CharField(max_length=64)
    rows=models.JSONField(default=list)
    errors=models.JSONField(default=list)
    schema_fingerprints=models.JSONField(default=dict)
    status=models.CharField(max_length=20,default='preview')
    result_ids=models.JSONField(default=list)
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    committed_at=models.DateTimeField(null=True,blank=True)
