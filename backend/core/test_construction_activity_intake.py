"""Real HTTP construction assignment and repeated test-report entry, isolated DB."""
import json
from copy import deepcopy
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.urls import reverse
from .models import Company,Project,Profile,ProjectMembership,ChecklistTemplate,Checklist
from .standard_checklists import build_standard
from .template_service import duplicate_revision,missing_required

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConstructionActivityIntakeTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Synthetic construction contractor')
        self.definition=build_standard('construction_inspection_all',stages=['field_density_test','foundation_concrete'])
        self.template=ChecklistTemplate.objects.create(name='Synthetic construction tests',definition=self.definition,published=True)
        self.project=Project.objects.create(name='Synthetic construction project',company=self.company,industry='construction',checklist_template=self.template)
        self.lead=self.person('construction_lead',Profile.Roles.TEAM_LEAD)
        self.engineer=self.person('construction_engineer',Profile.Roles.ENGINEER)
        self.quality=self.person('construction_quality',Profile.Roles.QUALITY_ENGINEER)
        self.client.force_login(self.lead)
    def person(self,name,role):
        user=User.objects.create_user(name)
        user.profile.role=role;user.profile.project=self.project;user.profile.company=self.company;user.profile.save()
        ProjectMembership.objects.create(user=user,project=self.project,is_active=True,is_primary=True)
        return user
    def assign(self,site='SYNTHETIC-CONSTRUCTION',workflow='construction_inspection'):
        return self.client.post(reverse('governance_assign'),{'project':self.project.pk,'engineer':self.engineer.pk,'site_id':site,'latitude':'24','longitude':'46','description':'Synthetic activity','workflow_type':workflow,'governance_mode':'independent','asset_reference':'Synthetic building zone A','l2_reviewer':self.quality.pk,'l3_approver':self.lead.pk,'client_review_required':'not_required','review_reason':'Synthetic project inspection plan; no customer release required.'})
    def checklist(self):
        response=self.assign();self.assertEqual(response.status_code,302,response.content)
        return Checklist.objects.get(site_id='SYNTHETIC-CONSTRUCTION')
    def save(self,survey,answers):
        return self.client.post(reverse('custom_checklist_save',args=[survey.pk]),json.dumps({'answers':answers}),content_type='application/json')
    def test_wrong_activity_workflow_blocked_before_assignment(self):
        response=self.assign(workflow='telecom_inspection')
        self.assertEqual(response.status_code,400)
        self.assertEqual(Checklist.objects.count(),0)
        self.template.refresh_from_db();self.assertEqual(self.template.definition,self.definition)
    def test_repeated_fdt_and_slump_rows_save_reload_and_remain_per_activity(self):
        survey=self.checklist();self.client.force_login(self.engineer)
        fdt=[{'layer':'Lift A','location':'Zone A','moisture':'8 percent','dry_density':'1.9 Mg/m3','criteria':'Approved ITP A','report':'SYN-FDT-01','decision':'Pending'},{'layer':'Lift B','location':'Zone B','report':'SYN-FDT-02','decision':'Not applicable','na_reason':'Excluded by approved ITP B'}]
        concrete=[{'location':'Foundation A','batch':'SYN-BATCH-1','slump':'90','units':'mm','criteria':'Approved mix document','report':'SYN-CON-01','decision':'Pending'},{'location':'Foundation B','batch':'SYN-BATCH-2','slump':'95','units':'mm','report':'SYN-CON-02','decision':'Pending'}]
        values={'field_density_test_test_register':fdt,'foundation_concrete_test_register':concrete}
        self.assertEqual(self.save(survey,values).status_code,200)
        survey.refresh_from_db();self.assertEqual(survey.answer_data['custom'],values)
        response=self.client.get(reverse('custom_checklist',args=[survey.pk]));self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['checklist'].answer_data['custom'],values)
        self.assertNotIn('batch',survey.answer_data['custom']['field_density_test_test_register'][0])
        self.assertEqual(survey.section_approvals,{})
        empty=deepcopy(survey);empty.answer_data={}
        self.assertTrue(any('Activity test-report register' in label for label in missing_required(empty)))
    def test_approved_records_and_published_snapshots_do_not_change(self):
        survey=self.checklist();before=deepcopy(survey.schema_snapshot)
        draft=duplicate_revision(self.template,self.lead)
        draft.definition=deepcopy(draft.definition);draft.definition['sections'][1]['fields'][0]['label']='Changed future draft only';draft.save()
        self.template.refresh_from_db();survey.refresh_from_db()
        self.assertEqual(self.template.definition,self.definition);self.assertEqual(survey.schema_snapshot,before)
        survey.status=Checklist.Status.FINAL;survey.answer_data={'custom':{'field_density_test_test_register':[{'report':'SYN-LOCKED','decision':'Pending'}]}};survey.save()
        self.client.force_login(self.engineer)
        self.assertEqual(self.save(survey,{'field_density_test_test_register':[{'report':'FORGED'}]}).status_code,403)
        survey.refresh_from_db();self.assertEqual(survey.answer_data['custom']['field_density_test_test_register'][0]['report'],'SYN-LOCKED')
        self.assertEqual(survey.schema_snapshot,before)
