"""Independent regression coverage for inference-only unsafe-answer recovery."""
import json
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from .photo_service import withhold_protected_answers, validate_drafts, analyze_photo
from .template_service import default_definition
from .models import Checklist, ChecklistTemplate, Profile, Project, PhotoEvidence, PhotoJob, PhotoDraft


def proposal(fid='height',value='12',**changes):
    result={'field_id':fid,'value':value,'evidence_match':'visible','visual_evidence':'A steel support stands on a square concrete base in the foreground.','reason':'The visible support and concrete base match the requested structural evidence.','uncertainty':'medium','missing_information':'A qualified reviewer must verify the field answer.','anomalies':[]}
    result.update(changes)
    return result


class PhotoRecoveryValidationTests(SimpleTestCase):
    def test_protected_answers_withheld_with_warning_without_weakening_strict_validator(self):
        for field in [{'id':'height','label':'Measured height','type':'number'},{'id':'height','label':'Date','type':'date'},{'id':'height','label':'Overview','type':'photo'},{'id':'height','label':'Site','type':'text','system':'site_id'}]:
            with self.subTest(field=field):
                raw={'drafts':[proposal()]}
                with self.assertRaises((ValueError,ValidationError)):
                    validate_drafts(deepcopy(raw),[field])
                withhold_protected_answers(raw,[field])
                draft=validate_drafts(raw,[field])[0]
                self.assertIsNone(draft['value'])
                self.assertEqual(draft['uncertainty'],'high')
                self.assertIn('AI answer withheld',draft['missing_information'])
                self.assertIn('verify',draft['missing_information'].lower())
                self.assertEqual(draft['evidence_match'],'visible')
                self.assertIn('concrete base',draft['visual_evidence'])

    def test_invalid_inspection_approval_na_select_and_table_answers_are_never_retained(self):
        cases=[({'id':'height','label':'Inspection','type':'inspection'},'Checked'),({'id':'height','label':'Inspection','type':'inspection'},{'result':'Checked','remarks':'Claimed pass'}),({'id':'height','label':'Inspection','type':'inspection'},{'result':'Not applicable','remarks':'Not visible'}),({'id':'height','label':'Inspection','type':'inspection'},{'result':'Defect found','remarks':'Visible rust','extra':'unsafe'}),({'id':'height','label':'Condition','type':'select','options':['Good','Repair']},'Unknown option'),({'id':'height','label':'Inventory','type':'table','columns':[{'id':'model','label':'Model'}]},'Wrong scalar'),({'id':'height','label':'Notes','type':'text'},'N/A')]
        for field,value in cases:
            with self.subTest(value=value,kind=field['type']):
                raw={'drafts':[proposal(value=value)]}
                withhold_protected_answers(raw,[field])
                draft=validate_drafts(raw,[field])[0]
                self.assertIsNone(draft['value'])
                self.assertIn('AI answer withheld',draft['missing_information'])

    def test_valid_safe_answer_is_not_modified(self):
        field={'id':'height','label':'Condition','type':'inspection'}
        raw={'drafts':[proposal(value={'result':'Defect found','remarks':'Visible surface corrosion'})]}
        original=deepcopy(raw)
        withhold_protected_answers(raw,[field])
        self.assertEqual(raw,original)
        self.assertEqual(validate_drafts(raw,[field]),original['drafts'])

    def test_normalizer_cannot_repair_invalid_metadata_or_unknown_duplicate_fields(self):
        field={'id':'height','label':'Height','type':'number'}
        invalid=[{'uncertainty':'certain'},{'uncertainty':[]},{'reason':None},{'missing_information':[]},{'visual_evidence':None},{'evidence_match':'guaranteed'},{'anomalies':[{'description':'issue','bbox':[0.8,0,0.8,0.2]}]},{'field_id':'unknown'}]
        for change in invalid:
            with self.subTest(change=change):
                raw={'drafts':[proposal(**change)]}
                withhold_protected_answers(raw,[field])
                with self.assertRaises((ValueError,TypeError,ValidationError)):
                    validate_drafts(raw,[field])
        raw={'drafts':[proposal(),proposal()]}
        withhold_protected_answers(raw,[field])
        with self.assertRaises(ValueError):
            validate_drafts(raw,[field])

    def test_recovery_never_turns_generic_or_insufficient_evidence_into_visible_match(self):
        field={'id':'height','label':'Height','type':'number'}
        raw={'drafts':[proposal(reason='visible evidence',visual_evidence='clearly visible')]}
        withhold_protected_answers(raw,[field])
        with self.assertRaises(ValueError):
            validate_drafts(raw,[field])
        raw={'drafts':[proposal(evidence_match='insufficient')]}
        withhold_protected_answers(raw,[field])
        self.assertEqual(validate_drafts(raw,[field])[0]['evidence_match'],'insufficient')
        self.assertIsNone(raw['drafts'][0]['value'])

    def test_full_canonical_catalog_is_passed_intact_to_metadata_matching(self):
        from .template_service import default_definition
        schema=default_definition()
        metadata={'caption':'An antenna is visible above a concrete foundation.','objects':['antenna','foundation'],'visible_text':[],'issues':[],'uncertainties':[]}
        photo=SimpleNamespace(pk=123,sha256='a'*64,analysis_signature='',analysis_metadata={})
        with patch('core.photo_metadata.extract_metadata',return_value=metadata) as extract,patch('core.photo_metadata.match_metadata',return_value=[]) as match:
            self.assertEqual(analyze_photo(photo,schema,'synthetic-model'),[])
        extract.assert_called_once()
        self.assertEqual(sum(len(s['fields']) for s in match.call_args.args[1]['sections']),181)
        self.assertEqual(match.call_args.args[1],schema)


    def test_full_canonical_batches_limit_output_pressure_without_omitting_fields(self):
        from .photo_service import field_batches
        schema=default_definition()
        expected=[field['id'] for section in schema['sections'] for field in section['fields']]
        batches=list(field_batches(schema))
        self.assertEqual(len(expected),181)
        self.assertEqual([field['id'] for batch in batches for field in batch],expected)
        self.assertTrue(all(1<=len(batch)<=12 for batch in batches))
        self.assertEqual(len(batches),16)

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_model_output_limit_raises_safe_diagnostic_without_partial_or_raw_text(self,native,vision):
        from .photo_service import PhotoProcessingError
        from PIL import Image
        data=BytesIO()
        Image.new('RGB',(20,20),'blue').save(data,format='PNG')
        sentinel='PRIVATE MODEL OUTPUT MUST NOT APPEAR IN DIAGNOSTICS'
        native.return_value={'done_reason':'length','message':{'content':sentinel}}
        schema={'sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        photo=SimpleNamespace(pk=123,sha256='a'*64,analysis_signature='',analysis_metadata={},preview=SimpleNamespace(open=lambda mode:BytesIO(data.getvalue())))
        with self.assertRaises(PhotoProcessingError) as caught:
            analyze_photo(photo,schema,'synthetic-model')
        self.assertEqual(caught.exception.code,'metadata_output_limit')
        self.assertIsNotNone(caught.exception.batch_index)
        self.assertNotIn(sentinel,str(caught.exception))
        self.assertNotIn(sentinel,caught.exception.safe_message)
        native.assert_called_once()


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StoredPhotoRecoverySafetyTests(TestCase):
    def test_injected_protected_or_approval_draft_cannot_be_accepted(self):
        user=User.objects.create_user('photo_recovery_engineer')
        schema={'title':'Recovery safety fixture','sections':[{'id':'general','title':'General','fields':[{'id':'height','label':'Measured height','type':'number'},{'id':'condition','label':'Condition','type':'inspection'}]}]}
        template=ChecklistTemplate.objects.create(name='Recovery safety fixture',definition=schema,published=True)
        project=Project.objects.create(name='Recovery safety project',checklist_template=template)
        user.profile.role=Profile.Roles.ENGINEER
        user.profile.project=project
        user.profile.save()
        checklist=Checklist.objects.create(user=user,project=project,site_id='SYNTHETIC-RECOVERY')
        photo=PhotoEvidence.objects.create(checklist=checklist,filename='synthetic.png',sha256='synthetic-recovery')
        job=PhotoJob.objects.create(checklist=checklist,requested_by=user,model='fixture',schema=schema)
        self.client.force_login(user)
        for fid,value in [('height','42'),('condition',{'result':'Checked','remarks':'Injected approval'})]:
            draft=PhotoDraft.objects.create(job=job,photo=photo,field_id=fid,label=fid,value=value,reason='Injected test record',uncertainty='high')
            response=self.client.post(reverse('photo_accept',args=[checklist.pk,draft.pk]))
            self.assertEqual(response.status_code,403)
            draft.refresh_from_db()
            self.assertEqual(draft.status,'pending')
        checklist.refresh_from_db()
        self.assertEqual(checklist.answer_data,{})
        self.assertEqual(checklist.section_approvals,{})
        self.assertEqual(checklist.review_history,[])
        self.assertEqual(checklist.status,Checklist.Status.DRAFT)

    @patch('core.photo_service.analyze_photo')
    def test_failed_photo_does_not_advance_progress_and_retry_keeps_completed_checkpoint(self,analyze):
        from .photo_queue import process_next
        from .models import PhotoPlacement
        user=User.objects.create_user('photo_checkpoint_engineer')
        schema={'title':'Checkpoint safety fixture','sections':[{'id':'general','title':'General','fields':[{'id':'overview','label':'Overview photo','type':'photo'}]}]}
        template=ChecklistTemplate.objects.create(name='Checkpoint safety fixture',definition=schema,published=True)
        project=Project.objects.create(name='Checkpoint safety project',checklist_template=template)
        user.profile.role=Profile.Roles.ENGINEER
        user.profile.project=project
        user.profile.save()
        checklist=Checklist.objects.create(user=user,project=project,site_id='SYNTHETIC-CHECKPOINT')
        first=PhotoEvidence.objects.create(checklist=checklist,filename='first.png',sha256='first-synthetic')
        second=PhotoEvidence.objects.create(checklist=checklist,filename='second.png',sha256='second-synthetic')
        job=PhotoJob.objects.create(checklist=checklist,requested_by=user,model='fixture',schema=schema,total=2)
        job.photos.add(first,second)
        analyze.side_effect=[[proposal('overview',None)],ValueError('Malformed structured response')]
        self.assertTrue(process_next())
        job.refresh_from_db()
        self.assertEqual(job.status,'failed')
        self.assertEqual(job.completed,1)
        self.assertEqual(job.processed_photo_ids,[first.pk])
        self.assertEqual(job.drafts.count(),1)
        self.assertEqual(PhotoPlacement.objects.filter(photo=first,status='proposed').count(),1)
        self.assertFalse(PhotoPlacement.objects.filter(photo=second).exists())
        reviewer=User.objects.create_user('photo_checkpoint_lead')
        reviewer.profile.role=Profile.Roles.TEAM_LEAD
        reviewer.profile.project=project
        reviewer.profile.save()
        self.client.force_login(reviewer)
        self.assertEqual(self.client.post(reverse('photo_retry',args=[checklist.pk,job.pk])).status_code,200)
        analyze.reset_mock()
        analyze.side_effect=None
        analyze.return_value=[]
        self.assertTrue(process_next())
        analyze.assert_called_once()
        self.assertEqual(analyze.call_args.args[0].pk,second.pk)
        job.refresh_from_db()
        self.assertEqual(job.status,'completed')
        self.assertEqual(job.completed,2)
        self.assertEqual(job.processed_photo_ids,[first.pk,second.pk])
        self.assertEqual(job.drafts.count(),1)
        checklist.refresh_from_db()
        self.assertEqual(checklist.answer_data,{})
        self.assertEqual(checklist.section_approvals,{})
        self.assertFalse(PhotoPlacement.objects.filter(status__in=['confirmed','manual']).exists())
