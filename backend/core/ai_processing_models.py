"""Company policy and durable AI execution receipts. No credentials or evidence in audits."""
from django.conf import settings
from django.db import models
from .revision_models import ImmutableRecord


class AIProcessingSettings(models.Model):
    company=models.OneToOneField('core.Company',on_delete=models.PROTECT,related_name='ai_processing_settings')
    enabled=models.BooleanField(default=False)
    primary_provider=models.CharField(max_length=24,choices=[('local','Local Ollama'),('https_ollama','Approved HTTPS Ollama API')],default='local')
    local_model=models.CharField(max_length=160,default='qwen3.5:4b')
    api_model=models.CharField(max_length=160,blank=True)
    api_endpoint=models.CharField(max_length=80,blank=True)
    allow_external_evidence=models.BooleanField(default=False)
    fallback_enabled=models.BooleanField(default=False)
    daily_request_limit=models.PositiveIntegerField(default=2000)
    request_timeout=models.PositiveIntegerField(default=120)
    version=models.PositiveIntegerField(default=1)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    updated_at=models.DateTimeField(auto_now=True)


class AIProcessingPolicy(ImmutableRecord):
    job=models.OneToOneField('core.SurveyProcessingJob',on_delete=models.PROTECT,related_name='provider_policy')
    company=models.ForeignKey('core.Company',on_delete=models.PROTECT)
    snapshot=models.JSONField()
    fingerprint=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)


class AIProcessingRequest(models.Model):
    policy=models.ForeignKey(AIProcessingPolicy,on_delete=models.PROTECT,related_name='requests')
    key=models.CharField(max_length=300)
    input_digest=models.CharField(max_length=64)
    state=models.CharField(max_length=16,default='pending')
    attempts=models.PositiveIntegerField(default=0)
    lease_token=models.CharField(max_length=32,blank=True)
    lease_until=models.DateTimeField(null=True)
    result=models.JSONField(null=True)
    result_digest=models.CharField(max_length=64,blank=True)
    error_code=models.CharField(max_length=40,blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['policy','key'],name='unique_ai_request_source')]


class AIProcessingQuota(models.Model):
    company=models.ForeignKey('core.Company',on_delete=models.PROTECT)
    day=models.DateField()
    used=models.PositiveIntegerField(default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['company','day'],name='unique_ai_daily_quota')]


class AIProcessingAttempt(models.Model):
    request=models.ForeignKey(AIProcessingRequest,on_delete=models.PROTECT,related_name='receipts')
    number=models.PositiveIntegerField()
    provider=models.CharField(max_length=24)
    model=models.CharField(max_length=160)
    outcome=models.CharField(max_length=16,default='running')
    error_code=models.CharField(max_length=40,blank=True)
    started_at=models.DateTimeField(auto_now_add=True)
    finished_at=models.DateTimeField(null=True)
    class Meta:
        ordering=['pk']
        constraints=[models.UniqueConstraint(fields=['request','number'],name='unique_ai_request_attempt')]
