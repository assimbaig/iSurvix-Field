"""Scoped outbound compute credentials; survey inputs/results remain on the server."""
import uuid
from django.conf import settings
from django.db import models, router


class RemoteWorkerProject(models.Model):
    project = models.OneToOneField('core.Project', on_delete=models.CASCADE, related_name='remote_worker_configuration')
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class RemoteWorkerCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=100)
    secret_hash = models.CharField(max_length=64)
    projects = models.ManyToManyField('core.Project', related_name='remote_worker_credentials')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # A bearer token must never acquire a different tenant when an account or
    # an empty legacy project is reassigned. Unknown historic bindings fail closed.
    issuing_company = models.ForeignKey('core.Company', null=True, blank=True,
        editable=False, on_delete=models.PROTECT, related_name='issued_worker_credentials')
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            database = kwargs.get('using') or self._state.db or router.db_for_write(type(self), instance=self)
            previous = type(self).objects.using(database).filter(pk=self.pk).values_list('issuing_company_id', flat=True)
            if previous.exists() and previous.first() != self.issuing_company_id:
                from django.core.exceptions import ValidationError
                raise ValidationError('Worker company bindings are immutable; issue a new scoped credential.')
        return super().save(*args, **kwargs)


class RemoteSurveyLease(models.Model):
    job = models.OneToOneField('core.SurveyProcessingJob', on_delete=models.PROTECT, related_name='remote_execution')
    credential = models.ForeignKey(RemoteWorkerCredential, null=True, on_delete=models.PROTECT)
    token = models.UUIDField(default=uuid.uuid4)
    versions = models.JSONField(default=dict)
    sources_prepared = models.BooleanField(default=False)
    mapping_prepared = models.BooleanField(default=False)
    heartbeat_at = models.DateTimeField(null=True)


class RemoteSurveyTask(models.Model):
    job = models.ForeignKey('core.SurveyProcessingJob', on_delete=models.PROTECT, related_name='remote_tasks')
    key = models.CharField(max_length=300)
    kind = models.CharField(max_length=12)
    payload = models.JSONField()
    image = models.FileField(upload_to='survey_processing/remote_inputs/', blank=True)
    image_sha256 = models.CharField(max_length=64, blank=True)
    image_size = models.PositiveIntegerField(default=0)
    completed_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['pk']
        constraints = [models.UniqueConstraint(fields=['job', 'key'], name='unique_remote_survey_task')]
