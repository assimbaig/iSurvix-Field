"""Preserve named owners; adopt only one unambiguous existing Admin affiliation."""
from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def assign_unambiguous_owners(apps,schema_editor):
    Project=apps.get_model('core','Project')
    Profile=apps.get_model('core','Profile')
    Membership=apps.get_model('core','ProjectMembership')
    Audit=apps.get_model('core','GovernanceAudit')
    alias=schema_editor.connection.alias;now=timezone.now()
    for project in Project.objects.using(alias).filter(administrator__isnull=True).iterator():
        grants=Membership.objects.using(alias).filter(project_id=project.pk,is_active=True).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=now))
        revoked=Membership.objects.using(alias).filter(project_id=project.pk).exclude(pk__in=grants.values('pk')).values_list('user_id',flat=True)
        affiliated=Q(user_id__in=grants.values_list('user_id',flat=True))|Q(project_id=project.pk)
        candidates=Profile.objects.using(alias).filter(affiliated,role='ADMIN',admin_industry_pending=False,is_locked=False,user__is_active=True,user__is_superuser=False).exclude(user_id__in=revoked)
        candidates=candidates.filter(Q(company_id=project.company_id)|Q(company__isnull=True,project__company_id=project.company_id))
        candidates=candidates.filter(Q(admin_industry__isnull=True)|Q(admin_industry__code=project.industry))
        owners=list(candidates.values_list('user_id',flat=True).distinct()[:2])
        if len(owners)==1:
            Project.objects.using(alias).filter(pk=project.pk,administrator__isnull=True).update(administrator_id=owners[0])
            Audit.objects.using(alias).create(action='project_owner_backfilled',actor_name='System',project_id=project.pk,details={'administrator_id':owners[0],'reason':'Only one existing active company/industry Admin affiliation; named owners were preserved.'})


class Migration(migrations.Migration):
    dependencies=[('core','0039_admin_invitation_before_project')]
    operations=[migrations.RunPython(assign_unambiguous_owners,migrations.RunPython.noop)]
