"""Owner requests and immutable host-update receipts; no privileged code runs in web."""
import uuid
from django.conf import settings
from django.db import models
from .revision_models import ImmutableRecord


def new_nonce():
    return uuid.uuid4().hex


class ServerUpdateRequest(models.Model):
    STATES=[('pending','Awaiting operator'),('verified','Package verified'),('applying','Applying update'),
            ('completed','Completed'),('failed','Stopped / failed'),('rolled_back','Original release recovered')]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    request_key=models.UUIDField(unique=True)
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    scope=models.CharField(max_length=24,default='installed-server',editable=False)
    source_release=models.CharField(max_length=40)
    target_release=models.CharField(max_length=40)
    manifest_sha256=models.CharField(max_length=64)
    catalog_sha256=models.CharField(max_length=64)
    release_record_sha256=models.CharField(max_length=64,blank=True)
    edition=models.CharField(max_length=16,choices=[('customer','Customer server'),('cloud','Cloud server')])
    nonce=models.CharField(max_length=32,default=new_nonce,editable=False)
    maintenance_confirmed=models.BooleanField(default=False)
    status=models.CharField(max_length=16,choices=STATES,default='pending')
    active=models.BooleanField(default=True,editable=False)
    last_sequence=models.PositiveIntegerField(default=0)
    error_code=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']
        constraints=[models.UniqueConstraint(fields=['scope'],condition=models.Q(active=True),name='one_active_server_update')]


class ServerUpdateEvent(ImmutableRecord):
    request=models.ForeignKey(ServerUpdateRequest,on_delete=models.PROTECT,related_name='events')
    sequence=models.PositiveIntegerField()
    status=models.CharField(max_length=16)
    error_code=models.CharField(max_length=40,blank=True)
    receipt_digest=models.CharField(max_length=64)
    details=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['sequence']
        constraints=[models.UniqueConstraint(fields=['request','sequence'],name='unique_server_update_event')]
