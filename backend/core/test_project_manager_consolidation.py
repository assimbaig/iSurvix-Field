"""Canonical Admin identity, bounded legacy scope and frozen v1 signatures."""
import copy
import importlib
import io
import json
import tempfile
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connection,connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from .access import can_access_project,role_for
from .governance_forms import InvitationForm
from .governance_views import issue_guard
from .independent_workflow import content_snapshot,review_revision,snapshot_digest
from .models import Checklist,Company,GovernanceAudit,Profile,Project,ProjectInvitation,ProjectMembership
from .revision_models import ChecklistReviewPolicy,RevisionDecision,SubmissionRevision


transition=importlib.import_module('core.migrations.0051_consolidate_project_manager_admin')


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False)
class ProjectManagerConsolidationTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic consolidation company')
        self.project=Project.objects.create(name='Synthetic consolidation project',company=self.company)
        self.owner=self.person('canonical_owner',Profile.Roles.ADMIN)
        self.pm=self.person('legacy_pm',Profile.Roles.PROJECT_MANAGER)
        self.engineer=self.person('consolidation_engineer',Profile.Roles.ENGINEER)
        self.lead=self.person('consolidation_lead',Profile.Roles.TEAM_LEAD)
        self.super=self.person('consolidation_super',Profile.Roles.SUPER_ADMIN,superuser=True)

    def person(self,name,role,superuser=False):
        user=User.objects.create_user(name,is_superuser=superuser,is_staff=superuser)
        user.profile.role=role;user.profile.company=self.company;user.profile.project=self.project
        user.profile.save()
        return user

    def migrate_identities(self):
        transition.consolidate_project_managers(apps,SimpleNamespace(connection=connection))
        # Callers must not keep using an old cached profile after any role edit.
        self.pm=User.objects.get(pk=self.pm.pk)

    def legacy_revision(self):
        schema={'sections':[{'id':'s','title':'General','fields':[{'id':'a','label':'Observation','type':'text'}]}]}
        checklist=Checklist.objects.create(user=self.engineer,project=self.project,site_id='LEGACY-NAMED',
            governance_mode='independent',status=Checklist.Status.SUBMITTED,schema_snapshot=schema,
            answer_data={'custom':{'a':'Original signed observation'}})
        policy=ChecklistReviewPolicy.objects.create(checklist=checklist,l2_reviewer=self.lead,l3_approver=self.pm,
            configured_by=self.owner,reason='Historical named reviewers',workflow_version=1)
        frozen=content_snapshot(checklist)
        revision=SubmissionRevision.objects.create(checklist=checklist,number=1,snapshot=frozen,digest=snapshot_digest(frozen),
            submitted_by=self.engineer,l2_reviewer=self.lead,l3_approver=self.pm,workflow_version=1)
        policy.current_revision=revision;policy.save()
        RevisionDecision.objects.create(revision=revision,action='submit',level='L1',actor=self.engineer)
        return checklist,revision

    def test_six_selectable_roles_and_no_legacy_invitation_authority(self):
        choices=dict(Profile._meta.get_field('role').choices)
        self.assertEqual(set(choices),{'ADMIN','SUPER_ADMIN','TEAM_LEAD','ENGINEER','QUALITY_ENGINEER','CLIENT'})
        self.assertEqual(choices['ADMIN'],'Admin / Project Manager')
        for actor in [self.owner,self.super]:
            self.assertNotIn(Profile.Roles.PROJECT_MANAGER,dict(InvitationForm(actor=actor).fields['role'].choices))
            with self.assertRaises(PermissionDenied):issue_guard(actor,self.project,Profile.Roles.PROJECT_MANAGER)
        self.assertNotIn(Profile.Roles.ADMIN,dict(InvitationForm(actor=self.owner).fields['role'].choices))
        self.assertIn(Profile.Roles.ADMIN,dict(InvitationForm(actor=self.super).fields['role'].choices))

    def test_admin_consolidation_does_not_grant_technical_template_qualification(self):
        from .models import ChecklistTemplate
        from .roadmap_service import qualify_template
        template=ChecklistTemplate.objects.create(name='Synthetic qualification boundary',published=True,
            definition={'sections':[{'id':'s','title':'General','fields':[{'id':'a','label':'Observation','type':'text'}]}]})
        self.project.checklist_template=template;self.project.save()
        self.migrate_identities()
        with self.assertRaises(PermissionDenied):
            qualify_template(self.pm,self.project,'telecom_survey','Recorded criteria','Recorded method','Recorded reason')
        record=qualify_template(self.lead,self.project,'telecom_survey','Recorded criteria','Recorded method','Recorded reason')
        self.assertEqual(record.reviewed_by_id,self.lead.pk)

    def test_migrated_pm_uses_existing_admin_workspace_without_ownership_or_global_promotion(self):
        self.migrate_identities()
        self.assertEqual(self.pm.profile.role,Profile.Roles.ADMIN)
        self.assertEqual(role_for(self.pm),Profile.Roles.ADMIN)
        self.project.refresh_from_db();self.assertEqual(self.project.administrator_id,self.owner.pk)
        self.assertTrue(can_access_project(self.pm,self.project))
        self.assertFalse(self.pm.is_superuser);self.assertFalse(self.pm.is_staff)
        self.client.force_login(self.pm)
        response=self.client.get(reverse('governance_home'))
        self.assertContains(response,'id="role-navigation"')
        self.assertContains(response,'aria-label="Logout"')
        self.assertEqual(response.context['role_design']['label'],'Admin')
        self.assertTrue(response.context['is_project_admin'])

    def test_transition_grant_is_expiry_revocation_company_and_project_bounded(self):
        self.migrate_identities()
        grant=ProjectMembership.objects.get(user=self.pm,project=self.project)
        self.assertTrue(grant.legacy_admin_access)
        ungranted=Project.objects.create(name='Same-company ungranted project',company=self.company)
        foreign=Project.objects.create(name='Foreign project',company=Company.objects.create(name='Foreign company'))
        self.assertFalse(can_access_project(self.pm,ungranted))
        ProjectMembership.objects.create(user=self.pm,project=foreign,legacy_admin_access=True)
        self.assertFalse(can_access_project(self.pm,foreign))
        grant.expires_at=timezone.now()-timedelta(seconds=1);grant.save()
        self.assertFalse(can_access_project(self.pm,self.project))
        grant.expires_at=None;grant.is_active=False;grant.save()
        self.assertFalse(can_access_project(self.pm,self.project))
        # A later ordinary membership cannot forge the migration delegation.
        ProjectMembership.objects.create(user=self.pm,project=ungranted)
        self.assertFalse(can_access_project(self.pm,ungranted))
        self.assertFalse(ProjectMembership._meta.get_field('legacy_admin_access').editable)

    def test_only_named_migrated_admin_can_finish_v1_and_snapshot_is_unchanged(self):
        checklist,revision=self.legacy_revision()
        before=copy.deepcopy(revision.snapshot);digest=revision.digest
        self.migrate_identities()
        self.assertEqual(content_snapshot(checklist),before)
        with self.assertRaises(PermissionDenied):review_revision(self.owner,checklist,revision.pk,'approve')
        review_revision(self.lead,checklist,revision.pk,'validate')
        with self.assertRaises(PermissionDenied):review_revision(self.owner,checklist,revision.pk,'approve')
        self.client.force_login(self.pm)
        response=self.client.get(reverse('roadmap_activity',args=[checklist.pk]))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['can_approve'])
        review_revision(self.pm,checklist,revision.pk,'approve')
        revision.refresh_from_db();checklist.refresh_from_db()
        self.assertEqual(revision.snapshot,before);self.assertEqual(revision.digest,digest)
        self.assertEqual(revision.workflow_version,1)
        self.assertEqual(list(revision.decisions.values_list('actor_id',flat=True)),[self.engineer.pk,self.lead.pk,self.pm.pk])
        self.assertEqual(checklist.status,Checklist.Status.FINAL)
        self.assertEqual(checklist.quality_approval,{})

    def test_dry_run_is_read_only_and_repeated_transition_is_idempotent(self):
        out=io.StringIO()
        counts=(ProjectMembership.objects.count(),GovernanceAudit.objects.count())
        call_command('audit_project_manager_migration',stdout=out)
        report=json.loads(out.getvalue())
        self.assertEqual(report['legacy_profiles'][0]['user_id'],self.pm.pk)
        self.assertIn('industry_binding_missing',report['legacy_profiles'][0]['review_required'])
        self.pm.profile.refresh_from_db();self.assertEqual(self.pm.profile.role,'project_manager')
        self.assertEqual(counts,(ProjectMembership.objects.count(),GovernanceAudit.objects.count()))
        self.migrate_identities()
        counts=(ProjectMembership.objects.count(),GovernanceAudit.objects.count())
        self.migrate_identities()
        self.assertEqual(counts,(ProjectMembership.objects.count(),GovernanceAudit.objects.count()))

    def test_pending_or_conflicting_binding_defers_transition_without_losing_legacy_scope(self):
        from .models import IndustryCatalog
        for pending in [True,False]:
            with self.subTest(pending=pending):
                self.pm.profile.admin_industry_pending=pending
                self.pm.profile.admin_industry=IndustryCatalog.objects.get(code='construction') if not pending else None
                self.pm.profile.save()
                before=set(self.pm.project_memberships.values_list('project_id',flat=True))
                transition.consolidate_project_managers(apps,SimpleNamespace(connection=connection))
                self.pm=User.objects.get(pk=self.pm.pk)
                self.assertEqual(self.pm.profile.role,'project_manager')
                self.assertTrue(can_access_project(self.pm,self.project))
                self.assertEqual(set(self.pm.project_memberships.values_list('project_id',flat=True)),before)
                report=transition.migration_impact(apps)
                self.assertEqual(report['legacy_profiles'][0]['transition_status'],'REQUIRE_ADMIN_SETUP')
        # An explicit reviewed correction makes the default dry-run retry visible
        # and --apply completes it without a guessed industry or owner transfer.
        self.pm.profile.admin_industry_pending=False
        self.pm.profile.admin_industry=IndustryCatalog.objects.get(code='telecom')
        self.pm.profile.save()
        out=io.StringIO();call_command('consolidate_project_managers',stdout=out)
        self.assertEqual(json.loads(out.getvalue())['legacy_profiles'][0]['transition_status'],'READY_WITH_EXISTING_SCOPE')
        self.pm.profile.refresh_from_db();self.assertEqual(self.pm.profile.role,'project_manager')
        call_command('consolidate_project_managers',apply=True,stdout=io.StringIO())
        self.pm=User.objects.get(pk=self.pm.pk)
        self.assertEqual(self.pm.profile.role,'ADMIN')
        self.assertTrue(can_access_project(self.pm,self.project))


class ProjectManagerPopulatedMigrationTests(unittest.TestCase):
    """Apply 0050 -> 0051 on a fresh private database, never roll back shared data."""
    def test_populated_migration_preserves_flags_ownership_history_and_revoked_grants(self):
        alias='pm_migration_'+uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix='ifield-pm-migration-') as directory:
            config=copy.deepcopy(connection.settings_dict)
            config['NAME']=str(Path(directory)/'migration.sqlite3')
            connections.databases[alias]=config
            database=connections[alias]
            try:
                executor=MigrationExecutor(database)
                executor.migrate([('core','0050_remote_worker_version_pin')])
                old=executor.loader.project_state([('core','0050_remote_worker_version_pin')]).apps
                U=old.get_model('auth','User');P=old.get_model('core','Profile');C=old.get_model('core','Company')
                ProjectModel=old.get_model('core','Project');M=old.get_model('core','ProjectMembership')
                Inv=old.get_model('core','ProjectInvitation');R=old.get_model('core','SubmissionRevision')
                Check=old.get_model('core','Checklist');Decision=old.get_model('core','RevisionDecision')
                owner=U.objects.using(alias).create(username='historic_owner',is_staff=False,is_superuser=False)
                pm=U.objects.using(alias).create(username='historic_pm',is_staff=False,is_superuser=False)
                company=C.objects.using(alias).create(name='Historical company')
                project=ProjectModel.objects.using(alias).create(name='Historical project',company_id=company.pk,administrator_id=owner.pk)
                revoked_project=ProjectModel.objects.using(alias).create(name='Revoked historical project',company_id=company.pk)
                extra=ProjectModel.objects.using(alias).create(name='Extra historical project',company_id=company.pk)
                profile=P.objects.using(alias).create(user_id=pm.pk,role='project_manager',company_id=company.pk,project_id=project.pk)
                revoked=M.objects.using(alias).create(user_id=pm.pk,project_id=revoked_project.pk,is_active=False)
                expiry=timezone.now()+timedelta(days=3)
                active=M.objects.using(alias).create(user_id=pm.pk,project_id=extra.pk,is_active=True,expires_at=expiry)
                checklist=Check.objects.using(alias).create(user_id=owner.pk,project_id=project.pk,site_id='MIGRATION-ONLY',governance_mode='independent')
                revision=R.objects.using(alias).create(checklist_id=checklist.pk,number=1,workflow_version=1,
                    snapshot={'role':'project_manager','answers':{'a':'Frozen original'}},digest='a'*64,
                    submitted_by_id=owner.pk,l2_reviewer_id=owner.pk,l3_approver_id=pm.pk)
                Decision.objects.using(alias).create(revision_id=revision.pk,action='approve',level='L3',actor_id=pm.pk,reason='Historical approval')
                frozen=list(R.objects.using(alias).values());signed=list(Decision.objects.using(alias).values())
                pending=Inv.objects.using(alias).create(token_hash='a'*64,email='synthetic@example.test',role='project_manager',
                    project_id=project.pk,created_by_id=owner.pk,expires_at=timezone.now()+timedelta(days=1))
                before_tables=set(database.introspection.table_names())
                out=io.StringIO()
                call_command('audit_project_manager_migration',database=alias,stdout=out)
                self.assertEqual(json.loads(out.getvalue())['legacy_profiles'][0]['user_id'],pm.pk)
                self.assertEqual(set(database.introspection.table_names()),before_tables)
                self.assertEqual(P.objects.using(alias).get(pk=profile.pk).role,'project_manager')
                executor=MigrationExecutor(database)
                executor.migrate([('core','0051_consolidate_project_manager_admin')])
                new=executor.loader.project_state([('core','0051_consolidate_project_manager_admin')]).apps
                new_p=new.get_model('core','Profile').objects.using(alias).get(pk=profile.pk)
                self.assertEqual(new_p.role,'ADMIN')
                self.assertIsNone(new_p.admin_industry_id)
                self.assertEqual(new.get_model('core','Project').objects.using(alias).get(pk=project.pk).administrator_id,owner.pk)
                new_user=new.get_model('auth','User').objects.using(alias).get(pk=pm.pk)
                self.assertFalse(new_user.is_superuser);self.assertFalse(new_user.is_staff)
                new_m=new.get_model('core','ProjectMembership')
                primary=new_m.objects.using(alias).get(user_id=pm.pk,project_id=project.pk)
                self.assertTrue(primary.legacy_admin_access)
                self.assertFalse(new_m.objects.using(alias).get(pk=revoked.pk).is_active)
                self.assertEqual(new_m.objects.using(alias).get(pk=active.pk).expires_at,expiry)
                self.assertEqual(list(new.get_model('core','SubmissionRevision').objects.using(alias).values()),frozen)
                self.assertEqual(list(new.get_model('core','RevisionDecision').objects.using(alias).values()),signed)
                retired=new.get_model('core','ProjectInvitation').objects.using(alias).get(pk=pending.pk)
                self.assertIsNotNone(retired.revoked_at)
                self.assertEqual(retired.role,'project_manager')
                audit=new.get_model('core','GovernanceAudit').objects.using(alias).get(action='project_manager_consolidated')
                self.assertEqual(audit.details['user_id'],pm.pk)
                self.assertIn('industry_binding_missing',audit.details['review_required'])
                transition.consolidate_project_managers(new,SimpleNamespace(connection=database))
                self.assertEqual(new.get_model('core','GovernanceAudit').objects.using(alias).filter(action='project_manager_consolidated').count(),1)
            finally:
                database.close()
                del connections[alias]
                connections.databases.pop(alias,None)
