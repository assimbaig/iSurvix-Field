"""Private reset outbox and bounded shared throttles; no bearer secrets stored."""
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountRecoveryRequest(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='account_recovery_requests')
    email_fingerprint=models.CharField(max_length=64)
    auth_fingerprint=models.CharField(max_length=64)
    token_fingerprint=models.CharField(max_length=64)
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True,blank=True)
    invalidated_at=models.DateTimeField(null=True,blank=True)
    status=models.CharField(max_length=12,default='queued',choices=[
        ('queued','Queued'),('sending','Sending'),('accepted','Accepted by Microsoft 365'),
        ('failed','Failed'),('uncertain','Send outcome uncertain'),('cancelled','Cancelled')])
    attempts=models.PositiveSmallIntegerField(default=0)
    available_at=models.DateTimeField(default=timezone.now)
    lease_id=models.UUIDField(null=True,blank=True)
    lease_expires_at=models.DateTimeField(null=True,blank=True)
    error_code=models.CharField(max_length=64,blank=True)
    accepted_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        ordering=['created_at','id']
        indexes=[models.Index(fields=['status','available_at'],name='recovery_mail_ready_idx')]


class AccountRecoveryThrottle(models.Model):
    key=models.CharField(primary_key=True,max_length=80)
    window_started_at=models.DateTimeField(default=timezone.now)
    hits=models.PositiveIntegerField(default=0)
