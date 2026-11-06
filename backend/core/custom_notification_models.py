"""Company-owned notification presentation and business-day schedule, no credentials."""
from datetime import time
from django.conf import settings
from django.db import models

class CompanyNotificationSettings(models.Model):
    company=models.OneToOneField('core.Company',on_delete=models.PROTECT,related_name='notification_settings')
    version=models.PositiveIntegerField(default=1)
    templates=models.JSONField(default=dict,blank=True)
    combined_daily_enabled=models.BooleanField(default=False)
    daily_time=models.TimeField(default=time(18,0))
    timezone_name=models.CharField(max_length=80,default='Asia/Riyadh')
    digest_started_at=models.DateTimeField(null=True,blank=True)
    last_digest_day=models.DateField(null=True,blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    updated_at=models.DateTimeField(auto_now=True)
