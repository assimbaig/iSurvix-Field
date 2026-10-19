"""Consent-based professional information; separate from authorization Profile."""
from django.conf import settings
from django.db import models
from django.db.models import Q,F

class WorkProfile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='work_profile')
    display_name=models.CharField(max_length=120,blank=True)
    headline=models.CharField(max_length=200,blank=True)
    bio=models.TextField(max_length=4000,blank=True)
    published=models.BooleanField(default=False,db_index=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):return self.display_name or self.user.get_full_name() or 'Project team member'

class ProfessionalExperience(models.Model):
    work_profile=models.ForeignKey(WorkProfile,on_delete=models.CASCADE,related_name='experiences')
    organization=models.CharField(max_length=160)
    job_title=models.CharField(max_length=160)
    start_date=models.DateField()
    end_date=models.DateField(null=True,blank=True)
    is_current=models.BooleanField(default=False)
    summary=models.TextField(max_length=3000,blank=True)
    qualifications=models.TextField(max_length=2000,blank=True)
    class Meta:
        ordering=['-is_current','-start_date','-pk']
        constraints=[models.CheckConstraint(condition=Q(end_date__isnull=True)|Q(end_date__gte=F('start_date')),name='experience_end_after_start'),models.CheckConstraint(condition=Q(is_current=False)|Q(end_date__isnull=True),name='current_experience_no_end')]
