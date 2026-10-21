"""Lifecycle, scoped adaptive recommendations, and one-page workbook contracts."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Company, Project, Profile, IndustryCatalog, ChecklistTemplate, Checklist
from .template_views import template_edit_digest
from .checklist_lifecycle import lifecycle
from .checklist_recommendations import recommend, create_recommended


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuidedChecklistTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='Guided test company')
        self.project=Project.objects.create(name='Guided test project',company=self.company,industry='telecom')
        self.admin=self.person('guided_admin',Profile.Roles.ADMIN)
        self.engineer=self.person('guided_engineer',Profile.Roles.ENGINEER)
        self.project.refresh_from_db()
        self.definition={'wizard_context':{'version':1,'industry':'telecom','workflow_type':'telecom_survey'},'sections':[
            {'id':'general','title':'General','fields':[{'id':'name','label':'Name','type':'text','required':True}]}]}
        self.source=ChecklistTemplate.objects.create(name='Unused published',definition=deepcopy(self.definition),created_by=self.admin,published=True)
        self.draft=ChecklistTemplate.objects.create(name='Unused draft',definition=deepcopy(self.definition),created_by=self.admin)
        self.client.force_login(self.admin)

    def person(self,name,role):
        user=User.objects.create_user(name)
        profile=user.profile;profile.project=self.project;profile.company=self.company;profile.role=role
        if role==Profile.Roles.ADMIN:profile.admin_industry=IndustryCatalog.objects.get(code='telecom')
        profile.save();return user

    def test_published_unused_must_be_unpublished_then_can_be_modified(self):
        self.source.name='Changed too soon'
        with self.assertRaises(ValidationError):self.source.save()
        self.source.refresh_from_db()
        lifecycle(self.admin,self.source.pk,'unpublish',template_edit_digest(self.source))
        self.source.refresh_from_db();self.assertFalse(self.source.published)
        page=self.client.get(reverse('checklist_wizard_edit',args=[self.source.pk]))
        self.assertEqual(page.status_code,200)
        self.client.post(reverse('checklist_wizard_edit',args=[self.source.pk]),{'action':'save','name':'Modified after unpublish',
            'definition':json.dumps(self.definition),'wizard_expected_digest':page.context['wizard_expected_digest']})
        self.source.refresh_from_db();self.assertEqual(self.source.name,'Modified after unpublish')

    def test_used_source_cannot_unpublish_edit_or_delete_and_disabled_retains_work(self):
        self.project.checklist_template=self.source;self.project.save()
        survey=Checklist.objects.create(project=self.project,user=self.engineer,site_id='PRESERVED-GUIDED',answer_data={'human':'yes'})
        original=deepcopy(survey.schema_snapshot)
        for action in ['delete','unpublish']:
            with self.assertRaises(ValidationError):lifecycle(self.admin,self.source.pk,action,template_edit_digest(self.source))
        with self.assertRaises(ValidationError):self.source.delete()
        self.assertEqual(self.client.get(reverse('checklist_wizard'),{'target':self.source.pk}).status_code,409)
        lifecycle(self.admin,self.source.pk,'disable',template_edit_digest(self.source))
        self.source.refresh_from_db();self.assertTrue(self.source.disabled)
        from .governance_forms import ProjectForm
        self.assertTrue(ProjectForm(instance=self.project,actor=self.admin).fields['checklist_template'].queryset.filter(pk=self.source.pk).exists())
        self.assertFalse(ProjectForm(actor=self.admin).fields['checklist_template'].queryset.filter(pk=self.source.pk).exists())
        survey.refresh_from_db();self.assertEqual(survey.schema_snapshot,original);self.assertEqual(survey.answer_data,{'human':'yes'})
        with self.assertRaises(ValidationError):Checklist.objects.create(project=self.project,user=self.engineer,site_id='NEW-BLOCKED')
        self.project.refresh_from_db();self.project.description='Other project settings still editable';self.project.save()
        lifecycle(self.admin,self.source.pk,'enable',template_edit_digest(self.source))

    def test_stale_and_unconfirmed_actions_do_not_mutate(self):
        with self.assertRaises(ValidationError):lifecycle(self.admin,self.draft.pk,'delete','old-token')
        response=self.client.post(reverse('checklist_templates'),{'action':'delete','selected':[self.draft.pk],
            'token_'+str(self.draft.pk):template_edit_digest(self.draft)})
        # POSTs from the library use the library endpoint, not legacy creation.
        self.assertTrue(ChecklistTemplate.objects.filter(pk=self.draft.pk).exists())

    def test_library_bulk_is_atomic_and_filters_are_real(self):
        used=self.source;self.project.checklist_template=used;self.project.save()
        Checklist.objects.create(project=self.project,user=self.engineer)
        url=reverse('checklist_library')
        response=self.client.post(url,{'action':'delete','confirm_delete':'yes','selected':[self.draft.pk,used.pk],
            'token_'+str(self.draft.pk):template_edit_digest(self.draft),'token_'+str(used.pk):template_edit_digest(used)})
        self.assertEqual(response.status_code,200)
        self.assertTrue(ChecklistTemplate.objects.filter(pk=self.draft.pk).exists())
        page=self.client.get(url,{'state':'Draft','q':'Unused draft'})
        self.assertContains(page,'Unused draft');self.assertNotContains(page,'Unused published')
        self.client.post(url,{'action':'delete','confirm_delete':'yes','selected':[self.draft.pk],
            'token_'+str(self.draft.pk):template_edit_digest(self.draft)})
        self.assertFalse(ChecklistTemplate.objects.filter(pk=self.draft.pk).exists())

    def test_engineer_and_super_admin_cannot_manage_templates_or_recommendations(self):
        for role in [Profile.Roles.ENGINEER,Profile.Roles.SUPER_ADMIN]:
            actor=self.person('guided_denied_'+role,role)
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('checklist_library')).status_code,403)
            self.assertEqual(self.client.post(reverse('checklist_wizard'),{'action':'recommend_sections','name':'Denied',
                'industry':'telecom','workflow_type':'telecom_survey'}).status_code,403)

    def test_recommendations_require_section_acceptance_and_preserve_point_rules(self):
        response=self.client.post(reverse('checklist_wizard'),{'action':'recommend_sections','name':'Recommended draft',
            'industry':'telecom','workflow_type':'telecom_survey'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Accept sections')
        catalog=recommend(self.admin,'telecom','telecom_survey')
        section=next(s for s in catalog['sections'] if s['fields'])
        point=section['fields'][0]
        draft=create_recommended(self.admin,'Guided accepted','telecom','telecom_survey',catalog['digest'],[section['id']],'',[point['id']],'[]')
        expected=deepcopy(point['field']);expected['id']=point['id']
        self.assertEqual(draft.definition['sections'][0]['fields'],[expected]);self.assertFalse(draft.published)
        with self.assertRaises(ValidationError):create_recommended(self.admin,'Bad point','telecom','telecom_survey',catalog['digest'],[section['id']],'',['foreign-point'],'[]')

    def test_learning_only_includes_permitted_enabled_published_checklists(self):
        definition={'wizard_context':self.definition['wizard_context'],'sections':[{'id':'new','title':'Private new practice',
            'fields':[{'id':'unique','label':'Custom newly published checkpoint','type':'text'}]}]}
        learned=ChecklistTemplate.objects.create(name='Learning draft',definition=definition,created_by=self.admin)
        before=recommend(self.admin,'telecom','telecom_survey')
        self.assertFalse(any(s['title']=='Private new practice' for s in before['sections']))
        learned.published=True;learned.save()
        after=recommend(self.admin,'telecom','telecom_survey')
        section=next(s for s in after['sections'] if s['title']=='Private new practice')
        self.assertEqual(section['uses'],1)
        learned.disabled=True;learned.save()
        self.assertFalse(any(s['title']=='Private new practice' for s in recommend(self.admin,'telecom','telecom_survey')['sections']))
        with self.assertRaises(ValidationError):create_recommended(self.admin,'Stale','telecom','telecom_survey',after['digest'],[section['id']],'',[],'[]')

    def test_custom_sections_and_points_have_typed_required_photo_rules(self):
        catalog=recommend(self.admin,'telecom','telecom_survey')
        from .checklist_recommendations import selected_sections
        section=selected_sections(catalog,[],'Own section')[0]
        items=[{'section':section['id'],'label':'Nameplate text and photograph','type':'text','required':True,'photo_required':True}]
        draft=create_recommended(self.admin,'Own points','telecom','telecom_survey',catalog['digest'],[],'Own section',[],json.dumps(items))
        field=draft.definition['sections'][0]['fields'][0]
        self.assertTrue(field['required']);self.assertTrue(field['photo_required']);self.assertEqual(field['type'],'text')

    def sample(self):
        return (Path(__file__).resolve().parents[1]/'static/core/templates/iSurvix_Checklist_One_Page.xlsx').read_bytes()

    def test_one_page_sample_imports_and_round_trips_existing_advanced_format(self):
        from .checklist_workbook import parse_workbook,export_workbook
        parsed=parse_workbook(self.sample())
        record=parsed['checklists'][0];fields=[f for s in record['definition']['sections'] for f in s['fields']]
        self.assertEqual(len(fields),5);self.assertEqual(fields[0]['type'],'text');self.assertTrue(fields[0]['photo_required'])
        self.assertFalse(fields[2]['required']);self.assertEqual(fields[-1]['type'],'photo')
        self.assertEqual(parse_workbook(export_workbook([record]))['checklists'][0]['definition']['sections'],record['definition']['sections'])
        response=self.client.post(reverse('checklist_wizard'),{'action':'preview_import','workbook':SimpleUploadedFile('OnePage.xlsx',self.sample())})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Review Excel import')

    def test_one_page_rejects_formula_unknown_input_and_duplicate_points(self):
        from openpyxl import load_workbook
        from .checklist_workbook import parse_workbook,WorkbookValidationError
        for cell,value in [('B8','=1+1'),('C8','executable'),('E8','Sometimes'),('B9','Site identification')]:
            book=load_workbook(BytesIO(self.sample()))
            if cell=='B9':book['Checklist']['A9']='General'
            book['Checklist'][cell]=value;out=BytesIO();book.save(out)
            with self.assertRaises(WorkbookValidationError):parse_workbook(out.getvalue())

    def test_reviewed_import_appends_to_draft_preserves_existing_and_is_idempotent(self):
        from .checklist_wizard_service import preview_import,commit_import
        before=deepcopy(self.draft.definition)
        batch=preview_import(self.admin,SimpleUploadedFile('Points.xlsx',self.sample()),self.draft.pk)
        self.draft.refresh_from_db();self.assertEqual(self.draft.definition,before)
        commit_import(self.admin,batch.pk,batch.payload_digest)
        self.draft.refresh_from_db();result=deepcopy(self.draft.definition)
        self.assertEqual(result['sections'][0]['fields'][0],before['sections'][0]['fields'][0])
        self.assertEqual(sum(len(s['fields']) for s in result['sections']),6)
        commit_import(self.admin,batch.pk,batch.payload_digest)
        self.draft.refresh_from_db();self.assertEqual(self.draft.definition,result)

    def test_import_cannot_overwrite_changed_or_published_target(self):
        from .checklist_wizard_service import preview_import,commit_import
        batch=preview_import(self.admin,SimpleUploadedFile('Points.xlsx',self.sample()),self.draft.pk)
        self.draft.name='Concurrent edit';self.draft.save()
        with self.assertRaises(ValidationError):commit_import(self.admin,batch.pk,batch.payload_digest)
        self.draft.published=True;self.draft.save()
        with self.assertRaises(ValidationError):preview_import(self.admin,SimpleUploadedFile('Points.xlsx',self.sample()),self.draft.pk)

    def test_foreign_published_checkpoints_are_not_learned_or_manageable(self):
        other=User.objects.create_user('guided_foreign_admin')
        company=Company.objects.create(name='Other guided company')
        project=Project.objects.create(name='Other guided project',company=company,industry='telecom')
        p=other.profile;p.project=project;p.company=company;p.role=Profile.Roles.ADMIN;p.admin_industry=IndustryCatalog.objects.get(code='telecom');p.save()
        definition={'wizard_context':self.definition['wizard_context'],'sections':[{'id':'foreign','title':'Foreign confidential section',
            'fields':[{'id':'point','label':'Private competitor check','type':'text'}]}]}
        source=ChecklistTemplate.objects.create(name='Foreign source',definition=definition,created_by=other,published=True)
        catalog=recommend(self.admin,'telecom','telecom_survey')
        self.assertFalse(any(s['title']=='Foreign confidential section' for s in catalog['sections']))
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):lifecycle(self.admin,source.pk,'unpublish',template_edit_digest(source))
