"""Proven legacy Client records are preserved without reclassifying tenant data."""
import importlib
from types import SimpleNamespace
from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Company,IndustryCatalog,Profile,Project,GovernanceAudit,ClientOrganization

class LegacyClientMigrationTests(TestCase):
    def setUp(self):
        self.industry=IndustryCatalog.objects.get_or_create(code='telecom',defaults={'name':'Telecom'})[0]
        self.tenant=Company.objects.create(name='Synthetic existing employer')
        self.actor=User.objects.create_user('synthetic_historical_super',is_superuser=True)
        self.admin=User.objects.create_user('synthetic_legacy_owner')
        self.admin.profile.role=Profile.Roles.ADMIN
        self.admin.profile.company=self.tenant
        self.admin.profile.admin_industry=self.industry
        self.admin.profile.save()
        self.migration=importlib.import_module('core.migrations.0033_preserve_legacy_clients')
    def old_client(self,name):
        company=Company.objects.create(name=name,description='Original customer description')
        GovernanceAudit.objects.create(action='company_created',actor=self.actor,details={'company_id':company.pk})
        return company
    def test_import_keeps_company_identity_original_creator_and_date(self):
        old=self.old_client('Synthetic previously added Client')
        unrelated=Company.objects.create(name='Synthetic unproven orphan')
        employer=self.old_client('Synthetic employer with project')
        Project.objects.create(name='Synthetic existing employer project',company=employer)
        before=list(Company.objects.order_by('pk').values())
        self.migration.preserve_legacy_clients(apps,SimpleNamespace(connection=connection))
        self.assertEqual(list(Company.objects.order_by('pk').values()),before)
        client=ClientOrganization.objects.get(legacy_company=old)
        self.assertEqual(client.company_id,self.tenant.pk)
        self.assertEqual(client.industry_id,self.industry.pk)
        self.assertEqual(client.created_by_id,self.actor.pk)
        self.assertEqual(client.description,old.description)
        self.assertEqual(client.created_at,old.created_at)
        self.assertFalse(ClientOrganization.objects.filter(legacy_company__in=[unrelated,employer]).exists())
        self.migration.preserve_legacy_clients(apps,SimpleNamespace(connection=connection))
        self.assertEqual(ClientOrganization.objects.count(),1)
    def test_ambiguous_admin_tenants_do_not_guess_customer_owner(self):
        old=self.old_client('Synthetic ambiguous Client')
        another=User.objects.create_user('synthetic_other_owner')
        another.profile.role=Profile.Roles.ADMIN
        another.profile.company=Company.objects.create(name='Synthetic other employer')
        another.profile.admin_industry=self.industry
        another.profile.save()
        self.migration.preserve_legacy_clients(apps,SimpleNamespace(connection=connection))
        self.assertFalse(ClientOrganization.objects.exists())
        self.assertTrue(Company.objects.filter(pk=old.pk).exists())
