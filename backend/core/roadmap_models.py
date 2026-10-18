"""Reviewed template applicability and traceable inspection findings."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from .revision_models import ImmutableRecord


class WorkflowTemplateQualification(ImmutableRecord):
    project=models.ForeignKey('core.Project',on_delete=models.PROTECT,related_name='template_qualifications')
    template=models.ForeignKey('core.ChecklistTemplate',on_delete=models.PROTECT)
    workflow_type=models.CharField(max_length=32)
    definition_digest=models.CharField(max_length=64)
    criteria_reference=models.TextField()
    inspection_method=models.TextField()
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    reviewed_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField()
    def save(self,*args,**kwargs):
        if self.pk:raise ValidationError('Technical qualification records are immutable; record a new review.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        raise ValidationError('Retain technical qualification history.')


class InspectionFinding(models.Model):
    checklist=models.ForeignKey('core.Checklist',on_delete=models.PROTECT,related_name='inspection_findings')
    description=models.TextField()
    severity=models.CharField(max_length=12,choices=[('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')])
    blocking=models.BooleanField(default=True)
    status=models.CharField(max_length=20,default='open')
    asset_reference=models.CharField(max_length=200,blank=True)
    photo_ids=models.JSONField(default=list)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    due_date=models.DateField(null=True,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)


class FindingEvent(ImmutableRecord):
    finding=models.ForeignKey(InspectionFinding,on_delete=models.PROTECT,related_name='events')
    action=models.CharField(max_length=20)
    reason=models.TextField()
    photo_ids=models.JSONField(default=list)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if self.pk:raise ValidationError('Finding events are append-only.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        raise ValidationError('Retain finding event history.')
