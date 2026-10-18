"""Immutable engineering submissions and append-only independent decisions."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class ImmutableQuerySet(models.QuerySet):
    def update(self,**kwargs):
        raise ValidationError('Frozen revision records cannot be changed.')
    def delete(self):
        raise ValidationError('Frozen revision records cannot be deleted.')
    def bulk_update(self,*args,**kwargs):
        raise ValidationError('Frozen revision records cannot be changed.')
    def bulk_create(self,objs,*args,**kwargs):
        if kwargs.get('update_conflicts'):
            raise ValidationError('Frozen revision records cannot be replaced by an upsert.')
        return super().bulk_create(objs,*args,**kwargs)

class ImmutableRecord(models.Model):
    objects=ImmutableQuerySet.as_manager()
    class Meta:
        abstract=True
    def save(self,*args,**kwargs):
        if not self._state.adding or self.pk is not None and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Frozen revision records cannot be changed.')
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):
        raise ValidationError('Frozen revision records cannot be deleted.')

class SubmissionRevision(ImmutableRecord):
    workflow_version=models.PositiveSmallIntegerField(default=1)
    checklist=models.ForeignKey('core.Checklist',on_delete=models.PROTECT,related_name='submission_revisions')
    number=models.PositiveIntegerField()
    parent=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='corrections')
    snapshot=models.JSONField(default=dict)
    digest=models.CharField(max_length=64)
    submitted_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='submitted_engineering_revisions')
    l2_reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='assigned_l2_revisions')
    l3_approver=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='assigned_l3_revisions')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['checklist_id','number']
        constraints=[models.UniqueConstraint(fields=['checklist','number'],name='unique_checklist_submission_number')]

class RevisionDecision(ImmutableRecord):
    revision=models.ForeignKey(SubmissionRevision,on_delete=models.PROTECT,related_name='decisions')
    action=models.CharField(max_length=20)
    level=models.CharField(max_length=2)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    reason=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['created_at','pk']
        constraints=[models.UniqueConstraint(fields=['revision','action'],name='unique_revision_decision_action')]

class ChecklistReviewPolicy(models.Model):
    workflow_version=models.PositiveSmallIntegerField(default=1)
    checklist=models.OneToOneField('core.Checklist',on_delete=models.PROTECT,related_name='review_policy')
    l2_reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='l2_review_policies')
    l3_approver=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='l3_review_policies')
    customer_reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT,related_name='customer_review_policies')
    customer_required=models.BooleanField(default=False)
    applicability_reason=models.TextField(blank=True)
    current_revision=models.ForeignKey(SubmissionRevision,null=True,blank=True,on_delete=models.PROTECT,related_name='current_policies')
    configured_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='configured_review_policies')
    reason=models.TextField()
    configured_at=models.DateTimeField(auto_now=True)
