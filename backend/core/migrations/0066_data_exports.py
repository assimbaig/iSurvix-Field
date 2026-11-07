import uuid
from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
 dependencies=[('core','0065_account_recovery'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
 operations=[
  migrations.CreateModel(name='DataExportWorkerLease',fields=[('key',models.CharField(default='data-exports',max_length=24,primary_key=True,serialize=False)),('token',models.UUIDField(null=True)),('expires_at',models.DateTimeField(null=True))]),
  migrations.CreateModel(name='DataExportJob',fields=[
   ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
   ('section',models.CharField(max_length=32)),('request_key',models.UUIDField()),('parameters',models.JSONField(default=dict)),('principal',models.JSONField(default=dict)),
   ('status',models.CharField(choices=[('queued','Queued'),('running','Preparing'),('ready','Ready'),('failed','Failed'),('expired','Expired')],default='queued',max_length=12)),
   ('schema_version',models.PositiveSmallIntegerField(default=1)),('row_count',models.PositiveIntegerField(default=0)),('source_digest',models.CharField(blank=True,max_length=64)),('file_name',models.CharField(blank=True,max_length=120)),('sha256',models.CharField(blank=True,max_length=64)),('byte_count',models.PositiveBigIntegerField(default=0)),('error',models.CharField(blank=True,max_length=240)),('attempts',models.PositiveSmallIntegerField(default=0)),('lease_token',models.UUIDField(null=True)),('lease_until',models.DateTimeField(null=True)),('created_at',models.DateTimeField(auto_now_add=True)),('completed_at',models.DateTimeField(null=True)),('expires_at',models.DateTimeField()),
   ('company',models.ForeignKey(null=True,on_delete=django.db.models.deletion.PROTECT,related_name='data_exports',to='core.company')),
   ('owner',models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name='data_exports',to=settings.AUTH_USER_MODEL)),
  ],options={'ordering':['-created_at','-pk'],'indexes':[models.Index(fields=['status','created_at'],name='export_status_queue'),models.Index(fields=['owner','-created_at'],name='export_owner_history')],'constraints':[models.UniqueConstraint(fields=('owner','request_key'),name='unique_actor_export_request')]})]
