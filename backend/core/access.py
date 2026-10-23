"""Shared project authorization. Legacy ADMIN is scoped Project Admin."""
from django.core.exceptions import PermissionDenied
from .models import Profile, Project
from django.utils import timezone


def is_super_admin(user):
    if not user or not user.is_authenticated or not user.is_active or not user.is_superuser:
        return False
    profile=getattr(user,'profile',None)
    return bool(profile and not profile.is_locked)


def role_for(user):
    if is_super_admin(user):
        return Profile.Roles.SUPER_ADMIN
    if not user or not user.is_authenticated or not user.is_active:
        return None
    profile = getattr(user,'profile',None)
    if not profile or profile.is_locked or profile.role==Profile.Roles.SUPER_ADMIN:
        return None
    return profile.role


def company_id_for(user):
    profile=getattr(user,'profile',None)
    if not profile:
        return None
    return profile.company_id or (profile.project.company_id if profile.project_id else None)


def accessible_projects(user):
    from django.db.models import Q
    from .models import ProjectMembership
    if is_super_admin(user):
        return Project.objects.all()
    role=role_for(user)
    if role not in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.ENGINEER,Profile.Roles.CLIENT,Profile.Roles.PROJECT_MANAGER}:
        return Project.objects.none()
    profile=user.profile
    if role==Profile.Roles.ADMIN and Profile.objects.filter(user=user,admin_industry_pending=True).exists():
        return Project.objects.none()
    memberships=ProjectMembership.objects.filter(user=user)
    active=memberships.filter(is_active=True).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).values_list('project_id',flat=True)
    condition=Q(pk__in=active)
    # Compatibility for legacy callers that set Profile.project directly. A revoked
    # explicit membership always wins and may never regain access through this path.
    if profile.project_id and not memberships.filter(project_id=profile.project_id).exists():
        condition|=Q(pk=profile.project_id)
    projects=Project.objects.filter(condition,company_id=company_id_for(user))
    if role==Profile.Roles.ADMIN:
        delegated=active.filter(legacy_admin_access=True).values_list('project_id',flat=True)
        projects=projects.filter(Q(administrator_id=user.pk)|Q(pk__in=delegated))
        industry=Profile.objects.filter(user=user).values_list('admin_industry__code',flat=True).first()
        if industry:projects=projects.filter(industry=industry)
    return projects.distinct()


def user_project_ids(user):
    return accessible_projects(user).values_list('pk',flat=True)


def can_access_project(user,project_or_id):
    project_id=getattr(project_or_id,'pk',project_or_id)
    return accessible_projects(user).filter(pk=project_id).exists()


def client_checklist_visibility(user):
    """Current task data is visible only after that exact revision was shared."""
    from django.db.models import Q,F
    from .models import Checklist
    historical=Q(review_route_record__isnull=True,status=Checklist.Status.FINAL)&(
        Q(governance_mode='legacy')|Q(review_policy__customer_reviewer=user))
    shared=Q(review_policy__customer_reviewer=user,
             review_route_record__events__from_stage='team_lead',
             review_route_record__events__to_stage='client',
             review_route_record__events__revision_id=F('review_route_record__revision_id'))&~Q(review_route_record__stage='engineer')
    return historical|shared


def project_role(user,project_or_id):
    return role_for(user) if can_access_project(user,project_or_id) else None


role_for_project=project_role


def users_for_project(project_or_id,roles=None,include_inactive=False):
    from django.contrib.auth.models import User
    from django.db.models import Q
    from .models import ProjectMembership
    project=project_or_id if isinstance(project_or_id,Project) else Project.objects.get(pk=project_or_id)
    revoked=ProjectMembership.objects.filter(project=project).filter(Q(is_active=False)|Q(expires_at__lte=timezone.now())).values_list('user_id',flat=True)
    scope=Q(project_memberships__project=project,project_memberships__is_active=True)|Q(profile__project=project)
    affiliation=(Q(profile__company__isnull=True,profile__project__company__isnull=True) if project.company_id is None else Q(profile__company_id=project.company_id)|Q(profile__company__isnull=True,profile__project__company_id=project.company_id))
    users=User.objects.filter(scope,affiliation).exclude(pk__in=revoked).distinct()
    if roles is not None:
        users=users.filter(profile__role__in=roles,is_superuser=False)
    return users if include_inactive else users.filter(is_active=True)


def managed_project_ids(user):
    if is_super_admin(user) or role_for(user)==Profile.Roles.ADMIN:
        return user_project_ids(user)
    return Project.objects.none().values_list('pk',flat=True)


def project_role_guard(user, project_or_id, roles):
    if not can_access_project(user,project_or_id) or (not is_super_admin(user) and role_for(user) not in roles):
        raise PermissionDenied('This action is outside your project role.')
    return True


def client_review_token(checklist):
    """Signed snapshot includes history so an unchanged timestamp cannot hide edits."""
    import hashlib
    import json
    from django.core import signing
    from .models import WorkAssignment
    activity=WorkAssignment.objects.filter(checklist_id=checklist.pk).values('status','completed_at').first()
    if activity and activity['completed_at']:
        activity['completed_at']=activity['completed_at'].isoformat()
    snapshot={'activity':activity,'id':checklist.pk,'status':checklist.status,'updated_at':checklist.updated_at.isoformat(),
        'schema':checklist.schema_snapshot,'answers':checklist.answer_data,
        'section_approvals':checklist.section_approvals,'history':checklist.review_history,
        'client_approval':checklist.client_approval,'client_review_required':checklist.client_review_required,
        'client_review_routed_at':checklist.client_review_routed_at.isoformat() if checklist.client_review_routed_at else None,
        'client_review_completed_at':checklist.client_review_completed_at.isoformat() if checklist.client_review_completed_at else None}
    digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return signing.Signer(salt='governance-client-review').sign(digest)
