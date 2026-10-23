"""Consolidate active identity without rewriting frozen engineering history.

Rollback is deliberately forward-only: recovering a previous identity requires
an independently verified pre-migration backup. Signed snapshots are unchanged.
"""
from django.db import migrations,models
from django.utils import timezone


def migration_impact(apps,using='default'):
    Profile=apps.get_model('core','Profile')
    Project=apps.get_model('core','Project')
    Membership=apps.get_model('core','ProjectMembership')
    Invitation=apps.get_model('core','ProjectInvitation')
    now=timezone.now()
    records=[]
    # Explicit pre-0051 columns also let the read-only command inspect a 0050
    # database using current application models, without selecting new fields.
    profiles=Profile.objects.using(using).filter(role='project_manager').select_related('project','admin_industry','user').only(
        'id','user_id','role','project_id','company_id','admin_industry_id','admin_industry_pending',
        'project__id','project__company_id','project__industry','admin_industry__id','admin_industry__code',
        'user__id','user__is_superuser','user__is_staff','user__is_active')
    for profile in profiles.iterator():
        company_id=profile.company_id or (profile.project.company_id if profile.project_id else None)
        grants=list(Membership.objects.using(using).filter(user_id=profile.user_id).select_related('project').only(
            'id','user_id','project_id','is_active','expires_at','project__id','project__company_id','project__industry'))
        grant_ids={grant.project_id for grant in grants}
        eligible=[grant for grant in grants if grant.project.company_id==company_id]
        primary=profile.project if profile.project_id and profile.project_id not in grant_ids and profile.project.company_id==company_id else None
        effective=[grant.project for grant in eligible if grant.is_active and (grant.expires_at is None or grant.expires_at>now)]
        if primary:effective.append(primary)
        industries=sorted({project.industry for project in effective})
        issues=[]
        if company_id is None:issues.append('company_binding_missing')
        if not profile.admin_industry_id:issues.append('industry_binding_missing')
        if len(industries)>1:issues.append('multiple_preexisting_industries')
        if profile.admin_industry_id and any(code!=profile.admin_industry.code for code in industries):issues.append('industry_binding_conflicts_with_existing_scope')
        if profile.admin_industry_pending:issues.append('industry_binding_pending')
        if len(eligible)!=len(grants):issues.append('foreign_company_memberships_remain_inaccessible')
        if profile.user.is_superuser or profile.user.is_staff:issues.append('preexisting_privilege_flags_require_separate_review')
        unresolved=bool({'industry_binding_pending','industry_binding_conflicts_with_existing_scope'}&set(issues))
        records.append({'profile_id':profile.pk,'user_id':profile.user_id,'primary_project_id':profile.project_id,
            'company_scope_id':company_id,'project_ids':sorted({project.pk for project in effective}),
            'preserved_inactive_or_expired_membership_ids':[grant.pk for grant in eligible if not grant.is_active or grant.expires_at is not None and grant.expires_at<=now],
            'industry_codes':industries,'review_required':issues,'is_active':profile.user.is_active,
            'transition_status':'REQUIRE_ADMIN_SETUP' if unresolved else 'READY_WITH_EXISTING_SCOPE'})
    pending=Invitation.objects.using(using).filter(role='project_manager',accepted_at__isnull=True,revoked_at__isnull=True)
    return {'legacy_profiles':records,'pending_legacy_invitation_ids':list(pending.values_list('pk',flat=True)),
        'policy':'Preserve explicit same-company project affiliations and named owners; retire outstanding PM invites for authorized Admin reissue; do not alter engineering history or privilege flags.'}


def consolidate_project_managers(apps,schema_editor):
    using=schema_editor.connection.alias
    Profile=apps.get_model('core','Profile')
    Membership=apps.get_model('core','ProjectMembership')
    Invitation=apps.get_model('core','ProjectInvitation')
    Audit=apps.get_model('core','GovernanceAudit')
    impact=migration_impact(apps,using)
    for record in impact['legacy_profiles']:
        profile=Profile.objects.using(using).get(pk=record['profile_id'])
        if record['transition_status']=='REQUIRE_ADMIN_SETUP':
            # Converting this profile would activate Admin filters that deny its
            # previous scope. Keep the bounded legacy identity until a reviewed
            # binding decision is made; never guess another industry or owner.
            Audit.objects.using(using).get_or_create(action='project_manager_requires_admin_setup',actor_name='System',
                project_id=profile.project_id,details=record)
            continue
        # Only affiliations already visible under the previous company boundary
        # become transition grants. Existing revoked/expired grants stay revoked.
        Membership.objects.using(using).filter(user_id=profile.user_id,project__company_id=record['company_scope_id']).update(legacy_admin_access=True)
        if profile.project_id and profile.project_id in record['project_ids']:
            Membership.objects.using(using).get_or_create(user_id=profile.user_id,project_id=profile.project_id,
                defaults={'legacy_admin_access':True,'is_active':True,'is_primary':True})
        Profile.objects.using(using).filter(pk=profile.pk,role='project_manager').update(role='ADMIN')
        Audit.objects.using(using).create(action='project_manager_consolidated',actor_name='System',
            project_id=profile.project_id,details={**record,'role_before':'project_manager','role_after':'ADMIN',
                'project_owners_changed':False,'engineering_history_changed':False,'privilege_flags_changed':False})
    # A former PM invitation could be issued by a non-global Admin. Converting
    # its role would silently authorize an Admin grant that issuer cannot make.
    # Retain its original role/history and require proper canonical reissue.
    now=timezone.now()
    for invitation in Invitation.objects.using(using).filter(pk__in=impact['pending_legacy_invitation_ids']):
        Invitation.objects.using(using).filter(pk=invitation.pk,accepted_at__isnull=True,revoked_at__isnull=True).update(revoked_at=now)
        Audit.objects.using(using).create(action='legacy_pm_invitation_retired',actor_name='System',project_id=invitation.project_id,
            details={'invitation_id':invitation.pk,'reason':'Reissue as canonical Admin through the authorized Super Admin grant flow.'})


class Migration(migrations.Migration):
    dependencies=[('core','0050_remote_worker_version_pin')]
    operations=[
        migrations.AddField(model_name='projectmembership',name='legacy_admin_access',field=models.BooleanField(default=False,editable=False)),
        migrations.AlterField(model_name='profile',name='role',field=models.CharField(max_length=20,choices=[
            ('ADMIN','Admin / Project Manager'),('SUPER_ADMIN','Super Admin'),('TEAM_LEAD','Team Lead'),
            ('ENGINEER','Engineer'),('QUALITY_ENGINEER','Quality Engineer'),('CLIENT','Client')])),
        migrations.RunPython(consolidate_project_managers),
    ]
