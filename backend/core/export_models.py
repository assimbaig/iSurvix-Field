"""Persistent, private, actor-owned data exports; source evidence is never modified."""
import uuid
from django.conf import settings
from django.db import models

class DataExportJob(models.Model):
 class Status(models.TextChoices):
  QUEUED='queued','Queued'
  RUNNING='running','Preparing'
  READY='ready','Ready'
  FAILED='failed','Failed'
  EXPIRED='expired','Expired'
 id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
 owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='data_exports')
 company=models.ForeignKey('core.Company',null=True,on_delete=models.PROTECT,related_name='data_exports')
 section=models.CharField(max_length=32)
 request_key=models.UUIDField()
 parameters=models.JSONField(default=dict)
 principal=models.JSONField(default=dict)
 status=models.CharField(max_length=12,choices=Status.choices,default=Status.QUEUED)
 schema_version=models.PositiveSmallIntegerField(default=1)
 row_count=models.PositiveIntegerField(default=0)
 source_digest=models.CharField(max_length=64,blank=True)
 file_name=models.CharField(max_length=120,blank=True)
 sha256=models.CharField(max_length=64,blank=True)
 byte_count=models.PositiveBigIntegerField(default=0)
 error=models.CharField(max_length=240,blank=True)
 attempts=models.PositiveSmallIntegerField(default=0)
 lease_token=models.UUIDField(null=True)
 lease_until=models.DateTimeField(null=True)
 created_at=models.DateTimeField(auto_now_add=True)
 completed_at=models.DateTimeField(null=True)
 expires_at=models.DateTimeField()
 class Meta:
  ordering=['-created_at','-pk']
  constraints=[models.UniqueConstraint(fields=['owner','request_key'],name='unique_actor_export_request')]
  indexes=[models.Index(fields=['status','created_at'],name='export_status_queue'),models.Index(fields=['owner','-created_at'],name='export_owner_history')]
 @property
 def available(self):
  from django.utils import timezone
  return self.status==self.Status.READY and self.expires_at>timezone.now()
 @property
 def display_status(self):
  from django.utils import timezone
  return 'Expired' if self.expires_at<=timezone.now() else self.get_status_display()
 def save(self,*args,**kwargs):
  if self.pk:
   old=type(self).objects.filter(pk=self.pk,status=self.Status.READY).first()
   if old and any(getattr(old,k)!=getattr(self,k) for k in ['owner_id','company_id','section','parameters','principal','schema_version','row_count','source_digest','file_name','sha256','byte_count','completed_at']):
    from django.core.exceptions import ValidationError
    raise ValidationError('Completed export contents are immutable. Request another export.')
  super().save(*args,**kwargs)

class DataExportWorkerLease(models.Model):
 key=models.CharField(max_length=24,primary_key=True,default='data-exports')
 token=models.UUIDField(null=True)
 expires_at=models.DateTimeField(null=True)
