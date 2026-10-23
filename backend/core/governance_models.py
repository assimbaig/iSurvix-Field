"""Invite-only membership and durable, credential-free governance audit."""
from django.conf import settings
from django.core.exceptions import ValidationError
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
        return {'ADMIN':'Admin / Project Manager','TEAM_LEAD':'Team Lead',
                'QUALITY_ENGINEER':'Quality Engineer','ENGINEER':'Engineer',
                'SUPER_ADMIN':'Super Admin','CLIENT':'Client',
                'project_manager':'Project Manager (legacy)'}.get(self.role,self.role)
    class Meta:
        ordering=['-created_at']

class GovernanceAuditQuerySet(models.QuerySet):
    """Protect event content through the application's ordinary ORM APIs.

    Nulling lifecycle references preserves the existing SET_NULL deletion
    contract. Snapshot content remains intact. Raw SQL/DBA access is a separate
    operational trust boundary, not made tamper-proof by these guards.
    """
    def update(self, **kwargs):
        lifecycle = {'actor', 'actor_id', 'project', 'project_id'}
        if not kwargs or not set(kwargs) <= lifecycle or any(value is not None for value in kwargs.values()):
            raise ValidationError('Audit events are append-only; record a new event.')
        return super().update(**kwargs)

    def delete(self):
        raise ValidationError('Audit events cannot be deleted through the application.')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('Audit events are append-only; record a new event.')

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False,
                    update_conflicts=False, update_fields=None, unique_fields=None):
        if update_conflicts:
            raise ValidationError('Audit events cannot be replaced by an upsert.')
        return super().bulk_create(
            objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts,
            update_conflicts=False, update_fields=update_fields,
            unique_fields=unique_fields,
        )


class GovernanceAudit(models.Model):
    objects = GovernanceAuditQuerySet.as_manager()
    action=models.CharField(max_length=80)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    actor_name=models.CharField(max_length=150,blank=True)
    project=models.ForeignKey('core.Project',null=True,on_delete=models.SET_NULL)
    details=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding or (self.pk is not None and type(self).objects.filter(pk=self.pk).exists()):
            raise ValidationError('Audit events are append-only; record a new event.')
        # Always INSERT: Model.save() otherwise tries UPDATE for an explicit PK,
        # allowing a concurrent insert between the existence check and the save
        # to be overwritten. Bind deprecated positional options too.
        if args:
            from inspect import signature
            bound = signature(super().save).bind_partial(*args, **kwargs)
            kwargs = dict(bound.arguments)
        if kwargs.get('force_update') or kwargs.get('update_fields') is not None:
            raise ValidationError('Audit events are append-only; record a new event.')
        kwargs['force_insert'] = True
        return super().save(**kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Audit events cannot be deleted through the application.')

    class Meta:
        ordering=['-created_at','-pk']
        base_manager_name = 'objects'

class GovernanceState(models.Model):
    key=models.CharField(max_length=32,primary_key=True)
    revision=models.PositiveBigIntegerField(default=0)
