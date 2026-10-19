"""Opt-in frozen task routing and append-only one-step clarification history."""
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from .revision_models import ImmutableRecord

class RouteQuerySet(models.QuerySet):
    def update(self,**kwargs):
        if set(kwargs)&{'layer_count','reviewers','checklist','checklist_id'}:raise ValidationError('Frozen task routing assignments cannot be changed.')
        return super().update(**kwargs)
    def bulk_update(self,objs,fields,*args,**kwargs):
        if set(fields)&{'layer_count','reviewers','checklist','checklist_id'}:raise ValidationError('Frozen task routing assignments cannot be changed.')
        return super().bulk_update(objs,fields,*args,**kwargs)

class ReviewRoute(models.Model):
    objects=RouteQuerySet.as_manager()
    checklist=models.OneToOneField('core.Checklist',on_delete=models.PROTECT,related_name='review_route_record')
    layer_count=models.PositiveSmallIntegerField()
    reviewers=models.JSONField(default=dict)
    stage=models.CharField(max_length=24,default='engineer')
    mode=models.CharField(max_length=16,default='review')
    revision=models.ForeignKey('core.SubmissionRevision',null=True,blank=True,on_delete=models.PROTECT,related_name='review_routes')
    generation=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if self.pk:
            old=type(self).objects.filter(pk=self.pk).values('layer_count','reviewers','checklist_id').first()
            if old and any(old[key]!=getattr(self,key) for key in old):raise ValidationError('Frozen task routing assignments cannot be changed.')
        return super().save(*args,**kwargs)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(layer_count__in=[3,4]),name='review_route_three_or_four_layers')]

class ReviewRouteEvent(ImmutableRecord):
    route=models.ForeignKey(ReviewRoute,on_delete=models.PROTECT,related_name='events')
    sequence=models.PositiveIntegerField()
    revision=models.ForeignKey('core.SubmissionRevision',null=True,blank=True,on_delete=models.PROTECT,related_name='route_events')
    revision_digest=models.CharField(max_length=64,blank=True)
    from_stage=models.CharField(max_length=24)
    to_stage=models.CharField(max_length=24)
    action=models.CharField(max_length=20)
    reason=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['sequence','pk']
        constraints=[models.UniqueConstraint(fields=['route','sequence'],name='unique_review_route_event_sequence')]
