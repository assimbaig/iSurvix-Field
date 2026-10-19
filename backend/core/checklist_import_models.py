"""Durable, actor-bound previews; imports only create unpublished definitions."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ChecklistImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    company = models.ForeignKey('core.Company', null=True, blank=True, on_delete=models.PROTECT)
    filename = models.CharField(max_length=255)
    upload_sha256 = models.CharField(max_length=64)
    payload = models.JSONField()
    payload_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    created_template_ids = models.JSONField(default=list)
    committed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            immutable = ('created_by_id', 'company_id', 'filename', 'upload_sha256',
                         'payload', 'payload_digest', 'created_at', 'expires_at')
            if any(getattr(original, key) != getattr(self, key) for key in immutable):
                raise ValidationError('An import preview is immutable. Upload the workbook again.')
            if original.committed_at and (self.committed_at != original.committed_at or
                                         self.created_template_ids != original.created_template_ids):
                raise ValidationError('A committed import cannot be changed.')
        return super().save(*args, **kwargs)
