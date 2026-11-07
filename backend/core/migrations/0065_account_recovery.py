"""Add private recovery state only; retained users/passwords/evidence unchanged."""
import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('core','0064_company_notification_settings'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(name='AccountRecoveryThrottle',fields=[
            ('key',models.CharField(max_length=80,primary_key=True,serialize=False)),
            ('window_started_at',models.DateTimeField(default=django.utils.timezone.now)),
            ('hits',models.PositiveIntegerField(default=0)),
        ]),
        migrations.CreateModel(name='AccountRecoveryRequest',fields=[
            ('id',models.UUIDField(default=uuid.uuid4,editable=False,primary_key=True,serialize=False)),
            ('email_fingerprint',models.CharField(max_length=64)),
            ('auth_fingerprint',models.CharField(max_length=64)),
            ('token_fingerprint',models.CharField(max_length=64)),
            ('expires_at',models.DateTimeField()),('used_at',models.DateTimeField(blank=True,null=True)),
            ('invalidated_at',models.DateTimeField(blank=True,null=True)),
            ('status',models.CharField(choices=[('queued','Queued'),('sending','Sending'),('accepted','Accepted by Microsoft 365'),('failed','Failed'),('uncertain','Send outcome uncertain'),('cancelled','Cancelled')],default='queued',max_length=12)),
            ('attempts',models.PositiveSmallIntegerField(default=0)),
            ('available_at',models.DateTimeField(default=django.utils.timezone.now)),
            ('lease_id',models.UUIDField(blank=True,null=True)),('lease_expires_at',models.DateTimeField(blank=True,null=True)),
            ('error_code',models.CharField(blank=True,max_length=64)),('accepted_at',models.DateTimeField(blank=True,null=True)),
            ('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),
            ('user',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='account_recovery_requests',to=settings.AUTH_USER_MODEL)),
        ],options={'ordering':['created_at','id'],'indexes':[models.Index(fields=['status','available_at'],name='recovery_mail_ready_idx')]}),
    ]
