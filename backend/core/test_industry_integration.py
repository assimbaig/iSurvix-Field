"""Industry rename retains workflow identity, project scope and frozen signatures."""
from django.test import TestCase,override_settings
from django.urls import reverse
from . import test_project_review_routes as fixtures
from .models import IndustryCatalog
from .access import accessible_projects
from .industry_service import industry_token

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
 PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndustryIntegrationTests(TestCase):
    setUp=fixtures.ProjectReviewRouteHttpTests.setUp
    person=fixtures.ProjectReviewRouteHttpTests.person
    prepared=fixtures.ProjectReviewRouteHttpTests.prepared
    submit=fixtures.ProjectReviewRouteHttpTests.submit
    action=fixtures.ProjectReviewRouteHttpTests.action
    stage=fixtures.ProjectReviewRouteHttpTests.stage
    def test_rename_preserves_admin_scope_standard_export_filters_and_frozen_approval(self):
        c=self.prepared(3);self.submit(c)
        original=c.schema_snapshot
        self.client.force_login(self.superuser)
        response=self.client.post(reverse('governance_industry'),{'industry_id':self.industry.pk,
            'expected_token':industry_token(self.industry),'code':'network_field','name':'Network Field',
            'description':'Scoped network field engineering work.','is_active':'on'})
        self.assertEqual(response.status_code,302,response.content)
        self.industry.refresh_from_db();c.project.refresh_from_db()
        self.assertEqual((self.industry.workflow_family,c.project.industry),('telecom','network_field'))
        self.assertTrue(accessible_projects(self.admin).filter(pk=c.project_id).exists())
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('standard_checklist_preview'),{'key':'telecom_survey_default'}).status_code,200)
        self.assertEqual(self.client.get(reverse('checklist_wizard_export',args=[c.checklist_template_id])).status_code,200)
        page=self.client.get(reverse('task_explorer'),{'module':'telecom_survey'})
        self.assertEqual(page.status_code,200);self.assertContains(page,'HTTP-ROUTE')
        for actor in [self.quality,self.lead]:self.assertEqual(self.action(c,actor,'approve').status_code,302)
        self.stage(c,'closed');c.refresh_from_db();self.assertEqual(c.schema_snapshot,original)
