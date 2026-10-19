"""Invite-only membership and durable, credential-free governance audit."""
from django.conf import settings
from django.db import models

class ProjectInvitation(models.Model):
    company=models.ForeignKey('core.Company',null=True,blank=True,on_delete=models.PROTECT,related_name='administration_invitations')
    admin_industry=models.ForeignKey('core.IndustryCatalog',null=True,blank=True,on_delete=models.PROTECT,related_name='admin_invitations')
    token_hash=models.CharField(max_length=64,unique=True)
    email=models.EmailField()
    role=models.CharField(max_length=20)
    project=models.ForeignKey('core.Project',null=True,blank=True,on_delete=models.CASCADE,related_name='invitations')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='created_project_invitations')
    expires_at=models.DateTimeField()
    accepted_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='accepted_project_invitations')
    accepted_at=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def get_role_display(self):
        return {'ADMIN':'Project Admin','TEAM_LEAD':'Team Lead','ENGINEER':'Engineer','SUPER_ADMIN':'Super Admin','CLIENT':'Client'}.get(self.role,self.role)
    class Meta:
        ordering=['-created_at']

class GovernanceAudit(models.Model):
    action=models.CharField(max_length=80)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    actor_name=models.CharField(max_length=150,blank=True)
    project=models.ForeignKey('core.Project',null=True,on_delete=models.SET_NULL)
    details=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at','-pk']

class GovernanceState(models.Model):
    key=models.CharField(max_length=32,primary_key=True)
    revision=models.PositiveBigIntegerField(default=0)
