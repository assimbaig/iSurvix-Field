"""Explicit same-company project grants; primary context never bypasses revocation."""
from django.core.exceptions import PermissionDenied,ValidationError
from .access import is_super_admin,role_for,can_access_project,company_id_for
from .models import Profile,ProjectMembership
from django.utils import timezone
from django.db.models import Q
from datetime import datetime


def grant_guard(actor,target,project,revoking=False):
    if is_super_admin(actor) and target.profile.role==Profile.Roles.CLIENT and not revoking:
        raise PermissionDenied('Only the scoped Project Admin may add Client project access.')
    if not is_super_admin(actor):
        if role_for(actor)!=Profile.Roles.ADMIN or not can_access_project(actor,project):
            raise PermissionDenied('Grant projects only within your assigned company projects.')
        if target.profile.role not in {Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER,Profile.Roles.QUALITY_ENGINEER} or target.is_superuser:
            raise PermissionDenied('Only Super Admin can assign administrator access.')
    if target.is_superuser or target.profile.role==Profile.Roles.SUPER_ADMIN:
        raise PermissionDenied('Super Admin does not use project membership grants.')
    industry=Profile.objects.filter(user=target,role=Profile.Roles.ADMIN).values_list('admin_industry__code',flat=True).first()
    if industry and industry!=project.industry and not revoking:
        raise ValidationError('This administrator is bound to another industry.')
    company=company_id_for(target)
    if company is not None and company!=project.company_id:
        raise ValidationError('This account belongs to another company.')
    # A legacy unclassified primary project is still an affiliation; never hide it
    # by silently moving the account to another company's security boundary.
    other=ProjectMembership.objects.filter(user=target,is_active=True).exclude(project__company_id=project.company_id).exists()
    primary=target.profile.project
    primary_grant=ProjectMembership.objects.filter(user=target,project=primary).first() if primary else None
    if other or (primary and (not primary_grant or primary_grant.is_active) and primary.company_id!=project.company_id):
        raise ValidationError('All active projects for this account must belong to the same company.')


def grant_membership(actor,target,project,make_primary=False,expires_at=None):
    grant_guard(actor,target,project)
    if expires_at is not None and (not isinstance(expires_at,datetime) or timezone.is_naive(expires_at) or expires_at<=timezone.now()):
        raise ValidationError('Choose a future expiry with a timezone, or leave it empty for an ongoing grant.')
    profile=target.profile
    if profile.company_id is None and project.company_id is not None:
        profile.company=project.company
    primary=make_primary or profile.project_id is None or profile.project_id==project.pk
    membership,_=ProjectMembership.objects.get_or_create(user=target,project=project,defaults={'granted_by':actor})
    membership.is_active=True
    membership.granted_by=actor
    membership.expires_at=expires_at
    if primary:
        ProjectMembership.objects.filter(user=target).update(is_primary=False)
        membership.is_primary=True
        profile.project=project
    membership.save()
    profile.save(update_fields=['company','project'])
    return membership


def revoke_membership(actor,target,project):
    grant_guard(actor,target,project,revoking=True)
    membership,_=ProjectMembership.objects.get_or_create(user=target,project=project,defaults={'is_active':False,'granted_by':actor})
    membership.is_active=False
    membership.is_primary=False
    membership.save(update_fields=['is_active','is_primary','updated_at'])
    profile=target.profile
    if profile.project_id==project.pk:
        replacement=ProjectMembership.objects.filter(user=target,is_active=True,project__company_id=project.company_id).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).select_related('project').order_by('created_at','pk').first()
        ProjectMembership.objects.filter(user=target).update(is_primary=False)
        profile.project=replacement.project if replacement else None
        profile.save(update_fields=['project'])
        if replacement:
            replacement.is_primary=True
            replacement.save(update_fields=['is_primary','updated_at'])
    if project.administrator_id==target.pk:
        project.administrator=None
        project.save(update_fields=['administrator'])
    return membership
