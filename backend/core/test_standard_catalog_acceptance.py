"""HTTP acceptance of scoped standard starters; no existing records are replaced."""
import json
import tempfile
import hashlib
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from .models import Company,Project,Profile,IndustryCatalog,ChecklistTemplate,Checklist,WorkAssignment
from .template_service import default_definition


KEYS=('telecom_survey_default','telecom_inspection_bts','telecom_inspection_colocation','construction_inspection_all')


@override_settings(SECRET_KEY='isolated-standard-catalog-tests',ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StandardCatalogAcceptanceTests(TestCase):
    def setUp(self):
        folder=Path(__file__).resolve().parents[2]/'.local/tmp';folder.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=folder,prefix='standard-catalog-')
        self.addCleanup(temporary.cleanup);storage=override_settings(MEDIA_ROOT=temporary.name)
        storage.enable();self.addCleanup(storage.disable)
        self.company=Company.objects.create(name='Synthetic standard catalog company')
        self.master=ChecklistTemplate.objects.create(name='Existing published source',definition=default_definition(),published=True)
        self.telecom=Project.objects.create(name='Synthetic telecom',company=self.company,industry='telecom',checklist_template=self.master)
        self.construction=Project.objects.create(name='Synthetic construction',company=self.company,industry='construction')
        self.superuser=self.person('super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.telecom_admin=self.person('telecom_admin',Profile.Roles.ADMIN,self.telecom,'telecom')
        self.construction_admin=self.person('construction_admin',Profile.Roles.ADMIN,self.construction,'construction')
        self.engineer=self.person('engineer',Profile.Roles.ENGINEER,self.telecom)
        self.lead=self.person('lead',Profile.Roles.TEAM_LEAD,self.telecom)
        self.quality=self.person('quality',Profile.Roles.QUALITY_ENGINEER,self.telecom)
        self.customer=self.person('customer',Profile.Roles.CLIENT,self.telecom)
        self.survey=Checklist.objects.create(project=self.telecom,user=self.engineer,quality_reviewer=self.quality,
            site_id='SYNTHETIC-EXISTING',answer_data={'custom':{'preserve':'Human existing answer'}},
            section_approvals={'preserve':{'by':self.lead.pk}},review_history=[{'action':'historical'}])
        self.task=WorkAssignment.objects.create(project=self.telecom,assigned_to=self.engineer,assigned_by=self.lead,
            site_id=self.survey.site_id,latitude=24,longitude=46,checklist=self.survey)

    def person(self,name,role,project=None,industry=None,superuser=False):
        user=User.objects.create_user('standard_'+name,is_superuser=superuser)
        user.profile.role=role;user.profile.project=project;user.profile.company=self.company
        if industry:user.profile.admin_industry=IndustryCatalog.objects.get(code=industry)
        user.profile.save();return user

    def create(self,key,name='Synthetic standard draft',**extra):
        return self.client.post(reverse('standard_checklists'),{'key':key,'name':name,**extra})

    def preview(self,key,**params):
        return self.client.get(reverse('standard_checklist_preview'),{'key':key,**params})

    def test_super_reads_all_four_entries_and_previews_but_cannot_create(self):
        self.client.force_login(self.superuser)
        response=self.client.get(reverse('standard_checklists'))
        self.assertEqual(response.status_code,200)
        before=ChecklistTemplate.objects.count()
        for key in KEYS:
            self.assertContains(response,key)
            self.assertEqual(self.preview(key).status_code,200,key)
            self.assertEqual(self.create(key).status_code,403,key)
        self.assertEqual(ChecklistTemplate.objects.count(),before)

    def test_bound_admin_industry_filters_catalog_and_denies_foreign_preview_and_create(self):
        for actor,allowed,denied in [(self.telecom_admin,KEYS[:3],KEYS[3:]),(self.construction_admin,KEYS[3:],KEYS[:3])]:
            self.client.force_login(actor)
            response=self.client.get(reverse('standard_checklists'));self.assertEqual(response.status_code,200)
            for key in allowed:self.assertContains(response,key)
            for key in denied:
                self.assertNotContains(response,key)
                self.assertIn(self.preview(key).status_code,[403,404])
                self.assertIn(self.create(key).status_code,[403,404])

    def test_other_roles_locked_and_forged_super_profile_do_not_create_or_read(self):
        for actor in [self.engineer,self.lead,self.quality,self.customer]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse('standard_checklists')).status_code,403)
            self.assertEqual(self.create(KEYS[0]).status_code,403)
        self.telecom_admin.profile.is_locked=True;self.telecom_admin.profile.save()
        self.client.force_login(self.telecom_admin)
        self.assertEqual(self.create(KEYS[0]).status_code,403)
        self.engineer.profile.role=Profile.Roles.SUPER_ADMIN;self.engineer.profile.save()
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('standard_checklists')).status_code,403)

    def test_csrf_is_required_and_invalid_requests_never_create_partial_drafts(self):
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.telecom_admin)
        self.assertEqual(secure.post(reverse('standard_checklists'),{'key':KEYS[0],'name':'No CSRF'}).status_code,403)
        self.client.force_login(self.construction_admin);before=ChecklistTemplate.objects.count()
        invalid=[{'key':KEYS[3],'rooms':'not-json'},
                 {'key':KEYS[3],'rooms':json.dumps({'type':'bedroom'})},
                 {'key':KEYS[3],'rooms':json.dumps([{'type':'unknown','name':'Unknown'}])},
                 {'key':KEYS[3],'rooms':json.dumps([{'type':'bedroom','name':'Invalid\x00room'}])},
                 {'key':KEYS[3],'rooms':json.dumps([{'type':'bedroom','name':'Room','floor':'1','admin':True}])},
                 {'key':KEYS[3],'rooms':json.dumps([{'type':'bedroom','name':'Room','floor':'1'}]*2)},
                 {'key':KEYS[3],'rooms':json.dumps([{'type':'bedroom','name':str(i)} for i in range(41)])},
                 {'key':KEYS[3],'stages':['unknown-stage']},
                 {'key':KEYS[3],'name':'x'*161}]
        for data in invalid:
            response=self.client.post(reverse('standard_checklists'),{'name':'Invalid draft','stages':['finishing'],**data})
            self.assertEqual(response.status_code,400,data)
        self.assertEqual(self.create('unknown').status_code,403)
        self.assertEqual(ChecklistTemplate.objects.count(),before)

    def test_csrf_valid_multipart_creation_preserves_normal_form_clients(self):
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.telecom_admin)
        page=secure.get(reverse('standard_checklists'));self.assertEqual(page.status_code,200)
        token=secure.cookies['csrftoken'].value
        response=secure.post(reverse('standard_checklists'),{'key':KEYS[1],'name':'CSRF multipart standard','csrfmiddlewaretoken':token})
        self.assertEqual(response.status_code,302,response.content)
        self.assertTrue(ChecklistTemplate.objects.filter(name='CSRF multipart standard').exists())

    def test_master_clone_is_fresh_draft_and_existing_source_assignments_and_answers_are_untouched(self):
        self.client.force_login(self.telecom_admin)
        source=deepcopy(self.master.definition);canonical=default_definition()
        source_branding=deepcopy(self.master.branding());historical_branding=deepcopy(self.survey.branding_snapshot)
        before=deepcopy((self.survey.schema_snapshot,self.survey.answer_data,self.survey.section_approvals,self.survey.review_history))
        response=self.create(KEYS[0],'Created standard survey')
        self.assertEqual(response.status_code,302,response.content)
        draft=ChecklistTemplate.objects.get(name='Created standard survey')
        self.assertFalse(draft.published);self.assertEqual(draft.version,1)
        self.assertNotEqual(draft.family_id,self.master.family_id);self.assertEqual(draft.created_by,self.telecom_admin)
        self.assertEqual(draft.definition['sections'],canonical['sections'])
        self.assertEqual((draft.client_left_name,draft.client_right_name),('',''))
        self.master.refresh_from_db();self.survey.refresh_from_db();self.telecom.refresh_from_db();self.task.refresh_from_db()
        self.assertEqual(self.master.definition,source);self.assertTrue(self.master.published)
        self.assertEqual(self.master.branding(),source_branding)
        self.assertEqual(self.survey.branding_snapshot,historical_branding)
        self.assertEqual(default_definition(),canonical)
        self.assertEqual((self.survey.schema_snapshot,self.survey.answer_data,self.survey.section_approvals,self.survey.review_history),before)
        self.assertEqual(self.telecom.checklist_template_id,self.master.pk)
        self.assertEqual(self.task.checklist_id,self.survey.pk)

    def test_construction_repeated_room_types_have_distinct_fields_results_and_wet_stair_topics(self):
        self.client.force_login(self.construction_admin)
        rooms=[{'type':'bedroom','name':'Bedroom','floor':'Ground'},
               {'type':'bedroom','name':'Bedroom','floor':'First'},
               {'type':'bathroom','name':'Bathroom','floor':'First'},
               {'type':'staircase','name':'Main stair','floor':'Ground to First'}]
        response=self.create(KEYS[3],'Multiroom draft',stages=['design','grey_structure','finishing'],rooms=json.dumps(rooms))
        self.assertEqual(response.status_code,302,response.content)
        draft=ChecklistTemplate.objects.get(name='Multiroom draft')
        fields=[field for section in draft.definition['sections'] for field in section['fields']]
        ids=[field['id'] for field in fields];self.assertEqual(len(ids),len(set(ids)))
        room_sections=[section for section in draft.definition['sections'] if section.get('room')]
        self.assertEqual(len(room_sections),4)
        self.assertEqual(len(set(section['id'] for section in room_sections)),4)
        self.assertEqual(draft.definition['standard_catalog']['rooms'],rooms)
        self.assertFalse(set(field['id'] for field in room_sections[0]['fields']) &
                         set(field['id'] for field in room_sections[1]['fields']))
        self.assertEqual(draft.definition['standard_catalog']['stages'],['design','grey_structure','finishing'])
        words=json.dumps(draft.definition).lower()
        for topic in ['bedroom','bathroom','stair','waterproof','grey']:self.assertIn(topic,words)
        self.assertEqual((draft.client_left_name,draft.client_right_name),('',''))
        self.assertEqual(Checklist.objects.count(),1)

    def test_preview_uses_actual_selected_stages_and_repeated_room_inventory_without_writes(self):
        self.client.force_login(self.construction_admin)
        rooms=[{'type':'bedroom','name':'Bedroom','floor':'Ground'},{'type':'bedroom','name':'Bedroom','floor':'First'}]
        before=ChecklistTemplate.objects.count()
        response=self.preview(KEYS[3],stages=['finishing'],rooms=json.dumps(rooms))
        self.assertEqual(response.status_code,200,response.content)
        definition=response.json()['definition']
        self.assertEqual(definition['standard_catalog']['stages'],['finishing'])
        self.assertEqual(definition['standard_catalog']['rooms'],rooms)
        self.assertEqual(len([s for s in definition['sections'] if s.get('room')]),2)
        self.assertEqual(ChecklistTemplate.objects.count(),before)

    def test_direct_model_writes_cannot_assign_standard_to_foreign_industry_or_wrong_workflow(self):
        from .standard_checklists import build_standard
        template=ChecklistTemplate.objects.create(name='Synthetic standard BTS published',published=True,
            definition=build_standard(KEYS[1]),client_left_name='',client_right_name='')
        with self.assertRaises(ValidationError):
            Project.objects.create(name='Wrong standard industry',industry='construction',company=self.company,checklist_template=template)
        project=Project.objects.create(name='Correct standard industry',industry='telecom',company=self.company,checklist_template=template)
        with self.assertRaises(ValidationError):
            Checklist.objects.create(project=project,user=self.engineer,site_id='WRONG-WORKFLOW',workflow_type='telecom_survey')
        self.assertFalse(Checklist.objects.filter(site_id='WRONG-WORKFLOW').exists())
        correct=Checklist.objects.create(project=project,user=self.engineer,site_id='RIGHT-WORKFLOW',workflow_type='telecom_inspection')
        self.assertEqual(correct.schema_snapshot['standard_catalog']['key'],KEYS[1])

    def test_forged_standard_metadata_is_rejected_before_template_creation(self):
        from .standard_checklists import build_standard
        definition=build_standard(KEYS[1]);definition['standard_catalog']['industry']='construction'
        with self.assertRaises(ValidationError):
            ChecklistTemplate.objects.create(name='Forged standard identity',definition=definition)
        self.assertFalse(ChecklistTemplate.objects.filter(name='Forged standard identity').exists())
        invalid=[{'stages':[]},{'stages':['unknown']},{'stages':['finishing','finishing']},
                 {'rooms':[{'type':'bathroom','name':'Bathroom '+str(i)} for i in range(41)]},
                 {'rooms':[{'type':'bathroom','name':'Bathroom','foreign_key':'untrusted'}]},
                 {'unknown_configuration':True}]
        for index,changes in enumerate(invalid):
            malformed=build_standard(KEYS[3]);malformed['standard_catalog'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                ChecklistTemplate.objects.create(name='Malformed published standard '+str(index),definition=malformed,published=True)
        bad_telecom=build_standard(KEYS[1]);bad_telecom['standard_catalog']['rooms']=[{'type':'bedroom','name':'Unexpected room'}]
        with self.assertRaises(ValidationError):
            ChecklistTemplate.objects.create(name='Telecom room configuration bypass',definition=bad_telecom)

    def test_generic_room_photo_cannot_identify_all_named_rooms_or_floors(self):
        from .standard_checklists import build_standard
        from .evidence_rules import evaluate_evidence
        rooms=[{'type':'bedroom','name':'Bedroom','floor':'Ground'},{'type':'bedroom','name':'Bedroom','floor':'First'}]
        definition=build_standard(KEYS[3],stages=['finishing'],rooms=rooms)
        observation={'caption':'A room floor, painted walls, ceiling and door are visible.',
                     'objects':['floor','wall','ceiling','door'],'visible_text':[],'issues':[],'uncertainties':[]}
        generic=evaluate_evidence(observation,definition)
        room_fields={f['id']:f['room_context'] for s in definition['sections'] for f in s['fields'] if f.get('room_context')}
        self.assertTrue(all(item['hard_blocked'] for item in generic if item['field_id'] in room_fields))
        named=evaluate_evidence({**observation,'visible_text':['Bedroom Ground']},definition)
        ground=[item for item in named if room_fields.get(item['field_id'],{}).get('floor')=='Ground']
        first=[item for item in named if room_fields.get(item['field_id'],{}).get('floor')=='First']
        self.assertTrue(ground);self.assertTrue(first)
        self.assertTrue(any(not item['hard_blocked'] for item in ground))
        self.assertTrue(all(item['hard_blocked'] for item in first))
        self.assertTrue(all(item['engineering_pass'] is None for item in named))

    def test_maximum_room_catalog_batches_semantic_tool_and_saves_every_field_assessment(self):
        from django.core.files.base import ContentFile
        from .standard_checklists import build_standard
        from .models import PhotoEvidence
        from .evidence_learning import find_analysis
        from . import evidence_pipeline as pipeline
        definition=build_standard(KEYS[3],rooms=[{'type':'bathroom','name':'Bathroom '+str(i),'floor':'First'} for i in range(40)])
        fields=[field for section in definition['sections'] for field in section['fields']]
        self.assertGreater(len(fields),500)
        template=ChecklistTemplate.objects.create(name='Maximum room standard',definition=definition,published=True)
        self.construction.checklist_template=template;self.construction.save()
        checklist=Checklist.objects.create(user=self.engineer,project=self.construction,site_id='MAXIMUM-ROOMS',workflow_type='construction_inspection')
        raw=b'Synthetic verified source; local image and semantic boundaries are mocked.'
        photo=PhotoEvidence.objects.create(checklist=checklist,filename='synthetic-source.png',sha256=hashlib.sha256(raw).hexdigest())
        photo.original.save('synthetic-source.png',ContentFile(raw))
        context={'rules_version':'subject-first-v1','model_version':'synthetic','model_digest':'a'*64,
                 'tool_version':'local-tools-v1','tool_fingerprint':'b'*64,'prompt_version':'subject-check-v1','release_id':None}
        observation={'caption':'An unidentifiable surface.','objects':[],'visible_text':[],'issues':[],'uncertainties':[]}
        seen=[];sizes=[]
        def semantic(metadata,batch,callback):
            sizes.append(len(batch));self.assertLessEqual(len(batch),500)
            seen.extend(field['id'] for field in batch)
            return {field['id']:0.0 for field in batch}
        with patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64),\
             patch('core.photo_metadata.extract_metadata',return_value=observation) as extract,\
             patch('core.local_evidence_tools.extract_local_tools',return_value={'quality':{},'capture_facts':{},'errors':[]}),\
             patch('core.local_evidence_tools.semantic_similarities',side_effect=semantic),\
             patch.object(pipeline,'targeted_vision',side_effect=lambda photo,model,request,check:{'assessments':[{'field_id':f['id'],'outcome':'insufficient','reason':'Synthetic unresolved subject','visible_evidence':'','missing_evidence':['Human source inspection']} for f in request['fields']]}):
            result=pipeline.analyze(photo,definition,'synthetic',context,lambda:None,None)
        self.assertEqual(extract.call_args.kwargs['image_source'],raw)
        self.assertEqual(len(sizes),2)
        self.assertEqual(seen,[field['id'] for field in fields])
        self.assertEqual(result,[])
        saved=find_analysis(checklist,photo,context)
        self.assertEqual({item['field_id'] for item in saved.payload['assessments']},set(seen))
        self.assertEqual(len(saved.payload['assessments']),len(fields))
        checklist.refresh_from_db();self.assertEqual(checklist.answer_data,{})
