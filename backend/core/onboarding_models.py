"""Controlled company intake; never a public sign-up or an operational project."""
import uuid
from django.conf import settings
from django.db import models


class CompanyApplication(models.Model):
    class Status(models.TextChoices):
        APPLIED = 'applied', 'Applied'
        REVIEWED = 'reviewed', 'Reviewed'
        PROVISIONED = 'provisioned', 'Provisioned'
        INVITED = 'invited', 'Invited'
        REJECTED = 'rejected', 'Rejected'

    request_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=160)
    name_key = models.CharField(max_length=320, db_index=True, editable=False)
    email = models.EmailField()
    industry = models.ForeignKey('core.IndustryCatalog', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLIED)
    company = models.OneToOneField('core.Company', null=True, blank=True, on_delete=models.PROTECT)
    invitation = models.OneToOneField('core.ProjectInvitation', null=True, blank=True, on_delete=models.PROTECT)
    review_note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_company_applications')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_company_applications')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['name_key'], condition=~models.Q(status='rejected'), name='one_open_company_application')]

    def __str__(self):
        return self.name
