"""Exact-revision editor, metadata, recommendations and branding integration."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import json,tempfile
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse
from PIL import Image
from .models import Company,Project,Profile,IndustryCatalog,ChecklistTemplate,Checklist
from .template_service import validate_definition


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ChecklistEditorTests(TestCase):
    def setUp(self):
        folder=Path(__file__).resolve().parents[2]/'.local/tmp';folder.mkdir(exist_ok=True,parents=True)
        temporary=tempfile.TemporaryDirectory(dir=folder,prefix='editor-test-');self.addCleanup(temporary.cleanup)
        override=override_settings(MEDIA_ROOT=temporary.name);override.enable();self.addCleanup(override.disable)
        self.company=Company.objects.create(name='Synthetic editor company')
        self.project=Project.objects.create(name='Synthetic editor project',company=self.company,industry='telecom')
        self.admin=User.objects.create_user('editor_admin')
        p=self.admin.profile;p.role=Profile.Roles.ADMIN;p.company=self.company;p.project=self.project;p.admin_industry=IndustryCatalog.objects.get(code='telecom');p.save()
        self.project.refresh_from_db()
        self.definition={'title':'Selected draft fields','wizard_context':{'version':1,'industry':'telecom','workflow_type':'telecom_survey'},'sections':[
            {'id':'civil','title':'Civil','group':'Site','fields':[{'id':'unique_civil','label':'Unique selected civil checkpoint','type':'text','required':True,'photo_required':True,'evidence_rules':{'version':1,'min_photos':2}}]},
            {'id':'power','title':'Power','group':'Site','fields':[{'id':'unique_power','label':'Selected power','type':'number','unit':'V'}]},
            {'id':'other','title':'Other','fields':[{'id':'unique_other','label':'Ungrouped condition','type':'inspection'}]}]}
        self.default=ChecklistTemplate.objects.create(name='Published default source',created_by=self.admin,published=True,definition=deepcopy(self.definition))
        self.selected=ChecklistTemplate.objects.create(name='5G7 - Existing Survey',created_by=self.admin,definition=deepcopy(self.definition))
        self.second=ChecklistTemplate.objects.create(name='Different draft',created_by=self.admin,definition={'sections':[{'id':'different','title':'Different data','fields':[{'id':'other_id','label':'Do not load this field','type':'text'}]}]})
        engineer=User.objects.create_user('editor_engineer');p=engineer.profile;p.role=Profile.Roles.ENGINEER;p.company=self.company;p.project=self.project;p.save()
        self.project.checklist_template=self.default;self.project.save()
        self.survey=Checklist.objects.create(project=self.project,user=engineer,site_id='PRESERVED-EDITOR',answer_data={'custom':{'unique_civil':'Saved human value'}})
        self.client.force_login(self.admin)

    def page(self,template=None,wizard=True):
        return self.client.get(reverse('checklist_wizard_edit' if wizard else 'checklist_template_edit',args=[(template or self.selected).pk]))

    def save(self,definition=None,template=None,**extra):
        template=template or self.selected;page=self.page(template)
        values={'action':'save','name':template.name,'definition':json.dumps(definition or template.definition),'editor_template_id':template.pk,
            'editor_version':template.version,'wizard_expected_digest':page.context['wizard_expected_digest']}
        values.update(extra)
        return self.client.post(reverse('checklist_wizard_edit',args=[template.pk]),values)

    def test_selected_draft_routes_identity_and_fields_stay_synchronized(self):
        response=self.client.post(reverse('checklist_wizard'),{'action':'edit','source_id':self.selected.pk})
        self.assertRedirects(response,reverse('checklist_wizard_edit',args=[self.selected.pk]))
        page=self.page();self.assertEqual(page.context['selected_template'].pk,self.selected.pk)
        self.assertContains(page,f'data-template-id="{self.selected.pk}"')
        self.assertContains(page,f'name="editor_template_id" value="{self.selected.pk}"')
        self.assertContains(page,'5G7 - Existing Survey');self.assertNotContains(page,'Do not load this field')
        self.assertIn('no-store',page['Cache-Control'])
        result=self.save(name='5G7 renamed');self.assertEqual(result.status_code,302)
        self.assertEqual(result.url,reverse('checklist_wizard_edit',args=[self.selected.pk]))
        self.assertEqual(self.page().context['selected_template'].name,'5G7 renamed')

    def test_mismatched_revision_cannot_save_into_another_source(self):
        for extra in [{'editor_template_id':self.second.pk},{'editor_version':999}]:
            self.assertEqual(self.save(name='Wrong revision',**extra).status_code,409)
        self.selected.refresh_from_db();self.assertEqual(self.selected.name,'5G7 - Existing Survey')

    def test_two_header_rows_collapsed_branding_and_separate_wizard_forms(self):
        page=self.page();self.assertContains(page,'editor-revision-row');self.assertContains(page,'editor-workflow-row')
        self.assertContains(page,'<details class="editor-branding" id="editor-branding">')
        self.assertNotContains(page,'<h2>Template details</h2>')
        self.assertContains(page,reverse('checklist_wizard')+'?target='+str(self.selected.pk))
        start=self.client.get(reverse('checklist_wizard'))
        self.assertContains(start,'wizard-existing-columns');self.assertContains(start,'Edit existing draft');self.assertContains(start,'Replicate checklist')

    def test_hierarchy_metadata_order_ids_and_evidence_round_trip(self):
        definition=deepcopy(self.selected.definition);definition['editor_groups']=['Power systems','Site','Empty group']
        definition['sections']=[definition['sections'][1],definition['sections'][0],definition['sections'][2]]
        definition['sections'][0]['group']='Power systems'
        self.assertEqual(self.save(definition).status_code,302)
        result=self.page().context['definition'];self.assertEqual(result,definition)
        self.assertEqual(result['sections'][1]['fields'][0]['evidence_rules'],{'version':1,'min_photos':2})
        definition['editor_groups'].remove('Site');definition['sections'][1]['group']=''
        self.selected.refresh_from_db();self.assertEqual(self.save(definition).status_code,302)
        saved=self.page().context['definition'];self.assertEqual(saved['sections'][1]['fields'][0]['id'],'unique_civil')
        self.survey.refresh_from_db();self.assertEqual(self.survey.answer_data,{'custom':{'unique_civil':'Saved human value'}})

    def test_invalid_group_parents_and_decisions_are_rejected(self):
        for metadata in [{'editor_groups':['Different']},{'editor_groups':['Site','site']},
            {'editor_recommendation_decisions':{'bad key':'accepted'}},{'editor_recommendation_decisions':{'p_1':'approved'}}]:
            definition={**deepcopy(self.definition),**metadata}
            with self.assertRaises(ValidationError):validate_definition(definition)

    def test_editor_metadata_and_recommendation_source_survive_excel(self):
        from .checklist_workbook import export_workbook,parse_workbook
        definition=deepcopy(self.definition);definition['editor_groups']=['Site','Empty group']
        definition['editor_recommendation_decisions']={'p_123':'accepted','p_456':'dismissed'}
        definition['sections'][0]['fields'][0]['recommendation_source']='Standard source'
        raw=export_workbook([{'key':'editor','name':'Editor','industry':'telecom','workflow_type':'telecom_survey','definition':definition}])
        result=parse_workbook(raw)['checklists'][0]['definition']
        self.assertEqual(result['editor_groups'],definition['editor_groups']);self.assertEqual(result['editor_recommendation_decisions'],definition['editor_recommendation_decisions'])
        self.assertEqual(result['sections'],definition['sections'])

    def test_recommendations_are_real_scoped_and_not_silently_applied(self):
        before=deepcopy(self.selected.definition)
        response=self.client.get(reverse('checklist_template_recommendations',args=[self.selected.pk]))
        self.assertEqual(response.status_code,200);result=response.json();self.assertEqual(result['template_id'],self.selected.pk)
        self.assertTrue(result['recommendations']);self.assertTrue(result['recommendations'][0]['source'].startswith(('Standard:','Published:')))
        self.selected.refresh_from_db();self.assertEqual(self.selected.definition,before)
        item=result['recommendations'][0];definition=deepcopy(before)
        definition['editor_recommendation_decisions']={item['id']:'accepted'}
        field=deepcopy(item['field']);field['id']='rec_'+item['id'][2:];field['label']='Accepted reviewed point'
        definition['sections'][0]['fields'].append(field)
        self.assertEqual(self.save(definition).status_code,302)
        self.selected.refresh_from_db();self.assertEqual(self.save().status_code,302)
        self.selected.refresh_from_db();self.assertEqual(sum(f['id']==field['id'] for s in self.selected.definition['sections'] for f in s['fields']),1)

    def test_recommendation_unavailable_returns_honest_error(self):
        with patch('core.editor_recommendations.additions',side_effect=ValidationError('No compatible library is available.')):
            response=self.client.get(reverse('checklist_template_recommendations',args=[self.selected.pk]))
        self.assertEqual(response.status_code,422);self.assertEqual(response.json()['recommendations'],[])

    def test_foreign_and_engineer_recommendation_access_are_denied(self):
        foreign=ChecklistTemplate.objects.create(name='Foreign draft',definition=self.definition)
        self.assertEqual(self.client.get(reverse('checklist_template_recommendations',args=[foreign.pk])).status_code,404)
        self.client.force_login(User.objects.get(username='editor_engineer'))
        self.assertEqual(self.client.get(reverse('checklist_template_recommendations',args=[self.selected.pk])).status_code,403)

    def logo(self,name,color):
        stream=BytesIO();Image.new('RGB',(80,25),color).save(stream,format='PNG')
        return SimpleUploadedFile(name,stream.getvalue(),content_type='image/png')

    def test_branding_upload_preserve_remove_and_historical_report_snapshot(self):
        response=self.save(company_logo=self.logo('company.png','green'),client_left_logo=self.logo('left.png','blue'),
            client_right_logo=self.logo('right.png','red'),client_left_name='Left client',client_right_name='Right client')
        self.assertEqual(response.status_code,302);self.selected.refresh_from_db()
        original=(self.selected.company_logo.name,self.selected.client_left_logo.name,self.selected.client_right_logo.name)
        self.assertEqual(self.save().status_code,302);self.selected.refresh_from_db()
        self.assertEqual(original,(self.selected.company_logo.name,self.selected.client_left_logo.name,self.selected.client_right_logo.name))
        self.assertEqual(self.selected.client_left_name,'Left client')
        self.assertEqual(self.save(remove_client_left_logo='on').status_code,302);self.selected.refresh_from_db()
        self.assertFalse(self.selected.client_left_logo);self.assertEqual(self.selected.company_logo.name,original[0])
        self.assertEqual(self.selected.client_right_logo.name,original[2])
        self.assertEqual(self.selected.branding()['company_logo'],original[0])
        self.survey.refresh_from_db();self.assertEqual(self.survey.branding_snapshot,self.default.branding())
        # Saved branding is consumed by the real report path, not just the editor.
        self.selected.published=True;self.selected.save()
        report=Checklist.objects.create(project=self.project,user=self.survey.user,site_id='SYNTHETIC-BRANDED',checklist_template=self.selected)
        from .template_service import export_custom_excel
        from openpyxl import load_workbook
        sheet=load_workbook(BytesIO(export_custom_excel(report))).active
        self.assertEqual(sheet['A1'].value,'Left client');self.assertEqual(sheet['D1'].value,'Right client')
        self.assertEqual(len(sheet._images),1)
        self.assertEqual((sheet._images[0].anchor._from.col,sheet._images[0].anchor._from.row),(3,1))

    def test_published_revision_cannot_change_hierarchy_or_accept_additions(self):
        original=deepcopy(self.default.definition)
        definition=deepcopy(original);definition['editor_groups']=['Site','Added group']
        self.save(definition,template=self.default)
        self.default.refresh_from_db();self.assertEqual(self.default.definition,original)
        self.assertContains(self.page(self.default),'data-locked="true"')
