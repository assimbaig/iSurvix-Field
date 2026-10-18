"""Independent selected-checklist QA; only synthetic database/media fixtures."""
import json
import tempfile
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from .models import Checklist, ChecklistTemplate, Profile, Project, WorkAssignment, GovernanceAudit
from .template_service import default_definition


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ChecklistSelectionTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory(prefix='selection-qa-',dir=Path(__file__).resolve().parents[2]/'.local')
        self.addCleanup(self.media.cleanup)
        self.storage=override_settings(MEDIA_ROOT=self.media.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        self.super=self.person('selection_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.project=Project.objects.create(name='Synthetic selection project')
        self.foreign_project=Project.objects.create(name='Foreign selection project')
        self.admin=self.person('selection_admin',Profile.Roles.ADMIN,self.project)
        self.engineer=self.person('selection_engineer',Profile.Roles.ENGINEER,self.project)
        self.lead=self.person('selection_lead',Profile.Roles.TEAM_LEAD,self.project)
        self.quality=self.person('selection_quality',Profile.Roles.QUALITY_ENGINEER,self.project)
        self.client_user=self.person('selection_client',Profile.Roles.CLIENT,self.project)
        self.foreign_admin=self.person('selection_foreign_admin',Profile.Roles.ADMIN,self.foreign_project)
        self.schema={'title':'Synthetic branded source','metadata':{'purpose':['preserve']},'sections':[
            {'id':'general','title':'General','group':'Site evidence','metadata':{'note':'keep'},'fields':[
                {'id':'site_id','label':'Site ID','type':'text','system':'site_id','required':True},
                {'id':'condition','label':'Condition','type':'select','options':['Good','Needs repair'],'required':True,'excel_row':7},
                {'id':'notes','label':'Notes','type':'textarea','required':False}]},
            {'id':'tower','title':'Tower','group':'Site evidence','fields':[
                {'id':'steel','label':'Steel condition','type':'inspection','required':True,'excel_row':12},
                {'id':'height','label':'Measured height','type':'number','required':False,'unit':'m','excel_row':13}]},
            {'id':'inventory','title':'Inventory','group':'Equipment','fields':[
                {'id':'equipment','label':'Equipment rows','type':'table','required':False,'columns':[{'id':'model','label':'Model'},{'id':'serial','label':'Serial'}]},
                {'id':'evidence','label':'Photo evidence','type':'photo','required':False}]}]}
        self.source=ChecklistTemplate.objects.create(name='Synthetic branded source',definition=deepcopy(self.schema),created_by=self.super,client_left_name='Synthetic Client A',client_right_name='Synthetic Client B')
        stream=BytesIO()
        Image.new('RGB',(10,10),'blue').save(stream,format='PNG')
        self.source.client_left_logo.save('synthetic-left.png',ContentFile(stream.getvalue()),save=False)
        self.source.client_right_logo.save('synthetic-right.png',ContentFile(stream.getvalue()),save=False)
        self.source.published=True
        self.source.save()
        self.project.checklist_template=self.source
        self.project.save()
        self.original=Checklist.objects.create(user=self.engineer,project=self.project,site_id='SYNTHETIC-EXISTING',status=Checklist.Status.FINAL,answer_data={'custom':{'condition':'Good'}},section_approvals={'general':{'by':self.lead.pk}},client_approval={'decision':'approved','reference':'Keep existing decision'})
        self.client.force_login(self.admin)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,password='Selection-fixture-481!')
        user.is_superuser=superuser
        user.save()
        user.profile.role=role
        user.profile.project=project
        user.profile.save()
        return user

    def select(self,fields=None,source=None,name='Synthetic selected draft',client=None):
        return (client or self.client).post(reverse('checklist_template_select'),{'source':str(source or self.source.pk),'name':name,'field_ids':fields if fields is not None else ['condition','steel']})

    def created(self,response):
        self.assertEqual(response.status_code,302,response.content[:500])
        return ChecklistTemplate.objects.exclude(pk=self.source.pk).latest('pk')

    def fields(self,schema):
        return [field for section in schema['sections'] for field in section['fields']]

    def test_master_catalog_remains_full_172_rows_and_inventories(self):
        before=default_definition()
        selected=[field['id'] for section in before['sections'] for field in section['fields'] if 'excel_row' in field][:2]
        response=self.select(selected,source='master')
        self.created(response)
        after=default_definition()
        self.assertEqual(after,before)
        fields=self.fields(after)
        self.assertEqual(sum('excel_row' in field for field in fields),172)
        self.assertEqual(sum(field['type']=='table' for field in fields),9)
        self.assertEqual(sum(field['type']=='inspection' for field in fields),150)

    def test_selected_leaf_ids_preserve_source_order_groups_and_full_field_metadata(self):
        chosen=['equipment','steel','condition','site_id']
        draft=self.created(self.select(chosen))
        expected=deepcopy(self.schema)
        for section in expected['sections']:
            section['fields']=[field for field in section['fields'] if field['id'] in chosen]
        self.assertEqual(draft.definition['sections'],expected['sections'])
        self.assertEqual(draft.definition['metadata'],self.schema['metadata'])
        self.assertEqual([field['id'] for field in self.fields(draft.definition)],['site_id','condition','steel','equipment'])
        draft.definition['sections'][0]['fields'][1]['options'].append('Draft only option')
        draft.definition['sections'][2]['fields'][0]['columns'][0]['label']='Draft column'
        draft.save()
        self.source.refresh_from_db()
        self.assertEqual(self.source.definition,self.schema)

    def test_subset_removes_empty_sections_and_section_selection_uses_leaf_ids(self):
        draft=self.created(self.select(['steel','height']))
        self.assertEqual([section['id'] for section in draft.definition['sections']],['tower'])
        self.assertEqual([field['id'] for field in self.fields(draft.definition)],['steel','height'])
        before=ChecklistTemplate.objects.count()
        response=self.select(['tower'])
        self.assertEqual(response.status_code,400)
        self.assertEqual(ChecklistTemplate.objects.count(),before)

    def test_empty_unknown_and_invalid_name_create_no_partial_drafts(self):
        before=ChecklistTemplate.objects.count()
        for fields,name in [([], 'Empty'),(['not-a-field'],'Unknown'),(['condition','not-a-field'],'Mixed'),(['condition'],''),(['condition'],'x'*161)]:
            with self.subTest(fields=fields,name=name):
                self.assertEqual(self.select(fields,name=name).status_code,400)
                self.assertEqual(ChecklistTemplate.objects.count(),before)

    def test_new_draft_has_fresh_family_branding_and_never_mutates_source_or_survey(self):
        source_values=deepcopy(self.source.__dict__)
        source_values.pop('_state')
        schema=deepcopy(self.original.schema_snapshot)
        branding=deepcopy(self.original.branding_snapshot)
        approval=deepcopy(self.original.section_approvals)
        draft=self.created(self.select())
        self.assertFalse(draft.published)
        self.assertEqual(draft.version,1)
        self.assertNotEqual(draft.family_id,self.source.family_id)
        self.assertEqual(draft.created_by,self.admin)
        self.assertEqual(draft.name,'Synthetic selected draft')
        self.assertEqual(draft.client_left_name,self.source.client_left_name)
        self.assertEqual(draft.client_right_name,self.source.client_right_name)
        self.assertEqual(draft.client_left_logo.name,self.source.client_left_logo.name)
        self.assertEqual(draft.client_right_logo.name,self.source.client_right_logo.name)
        self.source.refresh_from_db()
        for key,value in source_values.items():
            self.assertEqual(getattr(self.source,key),value,key)
        self.original.refresh_from_db()
        self.assertEqual(self.original.schema_snapshot,schema)
        self.assertEqual(self.original.branding_snapshot,branding)
        self.assertEqual(self.original.section_approvals,approval)
        self.assertEqual(self.original.answer_data,{'custom':{'condition':'Good'}})
        self.assertEqual(self.original.client_approval,{'decision':'approved','reference':'Keep existing decision'})
        self.assertEqual(self.original.status,Checklist.Status.FINAL)
        event=GovernanceAudit.objects.get(actor=self.admin,project=self.project,action='template_subset_created')
        self.assertEqual(event.details['template_id'],draft.pk)
        self.assertEqual(event.details['source_id'],self.source.pk)
        self.assertEqual(event.details['selected_field_ids'],['condition','steel'])
        self.assertEqual(len(event.details['selected_field_ids']),2)
        self.assertEqual(event.details['field_count'],2)
        self.assertEqual(event.details['section_count'],2)

    def test_selection_requires_authorized_unlocked_admin_and_csrf(self):
        for actor in [None,self.engineer,self.lead,self.client_user]:
            client=Client()
            if actor:
                client.force_login(actor)
            self.assertEqual(self.select(client=client).status_code,403)
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(self.select(client=strict).status_code,403)
        self.admin.profile.is_locked=True
        self.admin.profile.save()
        self.assertEqual(self.select().status_code,403)
        self.assertEqual(ChecklistTemplate.objects.count(),1)

    def test_project_admin_cannot_select_foreign_private_source(self):
        foreign=ChecklistTemplate.objects.create(name='Foreign private source',definition=deepcopy(self.schema),created_by=self.foreign_admin)
        self.assertEqual(self.select(source=foreign.pk).status_code,404)
        self.assertEqual(ChecklistTemplate.objects.count(),2)
        self.client.force_login(self.super)
        self.assertEqual(self.select(source=foreign.pk).status_code,403)
        self.client.force_login(self.foreign_admin)
        response=self.select(source=foreign.pk)
        self.assertEqual(response.status_code,302)
        self.assertEqual(ChecklistTemplate.objects.count(),3)

    def test_publish_assign_and_new_task_use_subset_existing_surveys_keep_full_snapshot(self):
        old_snapshot=deepcopy(self.original.schema_snapshot)
        draft=self.created(self.select(['site_id','condition']))
        editor=reverse('checklist_template_edit',args=[draft.pk])
        response=self.client.post(editor,{'action':'publish','name':draft.name,'definition':json.dumps(draft.definition),'client_left_name':draft.client_left_name,'client_right_name':draft.client_right_name})
        self.assertEqual(response.status_code,302)
        draft.refresh_from_db()
        self.assertTrue(draft.published)
        self.assertEqual(self.client.post(editor,{'action':'assign','project_id':self.foreign_project.pk}).status_code,404)
        self.assertEqual(self.client.post(editor,{'action':'assign','project_id':self.project.pk}).status_code,302)
        response=self.client.post(reverse('governance_assign'),{'project':self.project.pk,'engineer':self.engineer.pk,'quality_reviewer':self.quality.pk,'site_id':'SYNTHETIC-SUBSET-TASK','latitude':'24','longitude':'46','description':'Synthetic selected checklist task'})
        self.assertEqual(response.status_code,302)
        task=WorkAssignment.objects.get(site_id='SYNTHETIC-SUBSET-TASK')
        self.assertEqual(task.checklist.checklist_template,draft)
        self.assertEqual(task.checklist.schema_snapshot,draft.definition)
        self.assertEqual([field['id'] for field in self.fields(task.checklist.schema_snapshot)],['site_id','condition'])
        self.original.refresh_from_db()
        self.assertEqual(self.original.schema_snapshot,old_snapshot)
        self.assertEqual(len(self.fields(self.original.schema_snapshot)),7)

    def test_helper_exact_selection_deepcopy_and_malformed_ids(self):
        from .checklist_selection import subset_definition
        before=deepcopy(self.schema)
        result=subset_definition(self.schema,['equipment','condition'],'Helper selected')
        self.assertEqual([field['id'] for field in self.fields(result)],['condition','equipment'])
        self.assertEqual([section['id'] for section in result['sections']],['general','inventory'])
        self.assertEqual(result['sections'][0]['group'],'Site evidence')
        result['metadata']['purpose'].append('Draft only')
        result['sections'][0]['fields'][0]['options'].append('Draft only')
        result['sections'][1]['fields'][0]['columns'][0]['label']='Draft column'
        self.assertEqual(self.schema,before)
        for ids in [[],['condition','condition'],['unknown'],['tower'],[None],[1],['condition',{}],'condition',None]:
            with self.subTest(ids=ids):
                with self.assertRaises(ValidationError):
                    subset_definition(self.schema,ids,'Invalid helper test')

    def test_full_master_selection_preserves_every_leaf_and_section(self):
        master=default_definition()
        ids=[field['id'] for field in self.fields(master)]
        draft=self.created(self.select(ids,source='master',name='Full selected canonical catalog'))
        self.assertEqual(draft.definition['sections'],master['sections'])
        self.assertEqual(len(self.fields(draft.definition)),len(ids))
        self.assertEqual(len(draft.definition['sections']),len(master['sections']))

    def test_selection_catalog_get_is_scoped_and_reports_complete_dynamic_counts(self):
        foreign=ChecklistTemplate.objects.create(name='PRIVATE-UNRELATED-SELECTION-SOURCE',definition=deepcopy(self.schema),created_by=self.foreign_admin)
        response=self.client.get(reverse('checklist_template_select'))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,foreign.name)
        master=default_definition()
        self.assertEqual(response.context['selection_total_count'],len(self.fields(master)))
        self.assertEqual(response.context['selection_catalog'],master['sections'])
        self.assertContains(response,'csrfmiddlewaretoken')
        response=self.client.get(reverse('checklist_template_select'),{'source':self.source.pk})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['selection_total_count'],7)
        self.assertEqual(response.context['selection_catalog'],self.schema['sections'])
        for actor in [self.engineer,self.lead,self.client_user]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('checklist_template_select')).status_code,403)
