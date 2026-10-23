"""Independent QA using synthetic images and disposable database/media only."""
import json
import tempfile
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image
from .models import Checklist, ChecklistTemplate, Profile, Project
from .photo_service import prepare_image, verify_vision, field_batches, validate_drafts


class PhotoValidationTests(TestCase):
    def image(self, fmt='PNG'):
        stream = BytesIO()
        Image.new('RGB', (90, 60), 'blue').save(stream, format=fmt)
        return SimpleUploadedFile('synthetic.' + fmt.lower(), stream.getvalue(), content_type='image/png')

    def test_original_bytes_preserved_missing_exif_not_invented(self):
        image = self.image()
        original = image.read()
        image.seek(0)
        raw, preview, digest, metadata, advisories = prepare_image(image)
        self.assertEqual(raw, original)
        self.assertEqual(len(digest), 64)
        self.assertNotIn('gps', metadata)
        self.assertNotIn('captured_at', metadata)
        self.assertEqual(Image.open(BytesIO(preview)).format, 'JPEG')
        self.assertTrue(advisories)

    def test_corrupt_disguised_and_unsupported_images_rejected(self):
        for upload in [SimpleUploadedFile('photo.png', b'not an image'), self.image('GIF')]:
            with self.assertRaises(ValidationError):
                prepare_image(upload)

    def test_oversized_image_rejected(self):
        with self.assertRaises(ValidationError):
            prepare_image(SimpleUploadedFile('large.png', b'0' * (5 * 1024 * 1024 + 1)))

    @patch('core.photo_service.ollama')
    @patch('core.photo_service.installed_models')
    def test_missing_nonvision_and_remote_models_rejected(self, installed, call):
        installed.return_value = []
        with self.assertRaises(ValueError):
            verify_vision('unknown')
        call.assert_not_called()
        installed.return_value = ['local']
        for result in [{'capabilities':['completion']}, {'capabilities':['vision'], 'remote_host':'https://ollama.com'}]:
            call.return_value = result
            with self.assertRaises(ValueError):
                verify_vision('local')
        call.return_value = {'capabilities':['completion','vision']}
        self.assertIn('vision', verify_vision('local')['capabilities'])

    def test_catalog_batches_never_truncate(self):
        fields = [{'id':f'f{i}', 'type':'text', 'label':'x' * 100} for i in range(172)]
        batches = list(field_batches({'sections':[{'fields':fields}]}, limit=500))
        self.assertGreater(len(batches), 1)
        self.assertEqual([f['id'] for batch in batches for f in batch], [f['id'] for f in fields])
        with self.assertRaises(ValueError):
            list(field_batches({'sections':[{'fields':fields}]}, limit=10))

    def proposal(self, **changes):
        value = {'field_id':'condition', 'value':'Visible rust', 'reason':'Orange surface visible', 'uncertainty':'high', 'missing_information':'Close view needed', 'anomalies':[]}
        value.update(changes)
        return {'drafts':[value]}

    def test_untrusted_output_rejects_unknown_fields_types_and_anomalies(self):
        fields = [{'id':'condition','type':'text','label':'Condition'}]
        for result in [[], {'drafts':'bad'}, self.proposal(field_id='missing'), self.proposal(value=[]), self.proposal(uncertainty='certain'), self.proposal(anomalies=[{'description':'rust','bbox':[0.9,0,0.5,0.1]}]), self.proposal(value='N/A')]:
            with self.assertRaises((ValueError, ValidationError)):
                validate_drafts(result, fields)
        self.assertEqual(len(validate_drafts(self.proposal(), fields)), 1)

    def test_ai_cannot_supply_measurement_or_approval(self):
        for kind, value in [('number',12), ('date','2026-01-01'), ('inspection',{'result':'Pass','remarks':'Looks fine'})]:
            with self.assertRaises((ValueError, ValidationError)):
                validate_drafts(self.proposal(value=value), [{'id':'condition','type':kind,'label':'Condition'}])

@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False)
class PhotoWorkflowTests(PhotoValidationTests):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory(dir=str(__import__('pathlib').Path(__file__).resolve().parents[2] / '.local'))
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user('photo_engineer', password='Synthetic-726!')
        self.project = Project.objects.create(name='Synthetic photo project')
        self.user.profile.role = Profile.Roles.ENGINEER
        self.user.profile.project = self.project
        self.user.profile.save()
        self.reviewer=User.objects.create_user('photo_workflow_lead')
        self.reviewer.profile.role=Profile.Roles.TEAM_LEAD
        self.reviewer.profile.project=self.project
        self.reviewer.profile.save()
        self.schema = {'title':'Photo fixture','sections':[{'id':'general','title':'General','fields':[{'id':'condition','type':'text','label':'Condition'}]}]}
        template = ChecklistTemplate.objects.create(name='Photo fixture', definition=deepcopy(self.schema), published=True)
        self.project.checklist_template = template
        self.project.save()
        self.survey = Checklist.objects.create(project=self.project,user=self.user,site_id='SYNTHETIC-001')
        self.client.force_login(self.user)
        self.base = f'/local/photos/{self.survey.pk}/'

    def post_json(self, path, data=None, client=None):
        return (client or self.client).post(self.base+path,json.dumps(data or {}),content_type='application/json')

    def reviewer_json(self,path,data=None):
        self.client.force_login(self.reviewer)
        try:return self.post_json(path,data)
        finally:self.client.force_login(self.user)

    def upload(self):
        response = self.client.post(self.base+'upload/',{'files':[self.image()]})
        self.assertEqual(response.status_code,201,response.content)
        from .models import PhotoEvidence
        return PhotoEvidence.objects.get(pk=response.json()['photos'][0]['id'])

    def draft(self):
        from .models import PhotoJob, PhotoDraft
        photo = self.upload()
        job = PhotoJob.objects.create(checklist=self.survey,requested_by=self.user,model='local',schema=deepcopy(self.schema),baseline={},total=1)
        job.photos.add(photo)
        draft = PhotoDraft.objects.create(job=job,photo=photo,field_id='condition',label='Condition',value='Visible corrosion',reason='Surface discoloration',uncertainty='high',baseline_present=False)
        return job,draft

    def test_auth_csrf_and_project_scoping_all_photo_routes(self):
        job,draft = self.draft()
        paths = ['', 'state/','report/',f'evidence/{draft.photo_id}/original/']
        for path in paths:
            self.assertEqual(Client().get(self.base+path).status_code,404)
        outsider = User.objects.create_user('outsider')
        self.client.force_login(outsider)
        for path in paths:
            self.assertEqual(self.client.get(self.base+path).status_code,404)
        for path in ['upload/','enqueue/',f'jobs/{job.pk}/retry/',f'drafts/{draft.pk}/accept/']:
            self.assertEqual(self.post_json(path).status_code,404)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for path in ['upload/','enqueue/',f'jobs/{job.pk}/retry/',f'drafts/{draft.pk}/accept/']:
            self.assertEqual(self.post_json(path,client=strict).status_code,403)

    def test_duplicate_atomic_invalid_batch_and_original_download(self):
        photo = self.upload()
        response = self.client.post(self.base+'upload/',{'files':[self.image()]})
        self.assertTrue(response.json()['photos'][0]['duplicate'])
        self.assertEqual(self.survey.photo_evidence.count(),1)
        response = self.client.post(self.base+'upload/',{'files':[self.image(),SimpleUploadedFile('bad.png',b'bad')]})
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.survey.photo_evidence.count(),1)
        response = self.client.get(self.base+f'evidence/{photo.pk}/original/')
        self.assertEqual(b''.join(response.streaming_content),self.image().read())
        self.assertEqual(response['Cache-Control'],'private, no-store')

    def test_accept_explicit_once_keeps_approval_and_audit(self):
        job,draft = self.draft()
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{})
        response = self.reviewer_json(f'drafts/{draft.pk}/accept/')
        self.assertEqual(response.status_code,200,response.content)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data['custom']['condition'],'Visible corrosion')
        self.assertEqual(self.survey.section_approvals,{})
        self.assertEqual(self.survey.status,Checklist.Status.DRAFT)
        self.assertEqual(self.survey.review_history[-1]['action'],'accept_photo_draft')
        self.assertEqual(self.reviewer_json(f'drafts/{draft.pk}/accept/').status_code,409)

    def test_stale_missing_and_approved_fields_block_accept(self):
        job,draft = self.draft()
        self.survey.answer_data={'custom':{'condition':'Human changed'}}
        self.survey.save()
        self.assertEqual(self.reviewer_json(f'drafts/{draft.pk}/accept/').status_code,409)
        self.survey.answer_data={}
        self.survey.section_approvals={'general':{'by':'Reviewer'}}
        self.survey.save()
        self.assertEqual(self.reviewer_json(f'drafts/{draft.pk}/accept/').status_code,409)
        self.survey.section_approvals={}
        self.survey.save()
        draft.field_id='missing'
        draft.save()
        self.assertEqual(self.reviewer_json(f'drafts/{draft.pk}/accept/').status_code,409)

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_native_image_payload_and_malformed_model(self,call,vision):
        from .photo_service import analyze_photo
        photo=self.upload()
        metadata={'caption':'A concrete foundation supports the visible structure.','objects':['concrete foundation'],'visible_text':[],'issues':[],'uncertainties':[]}
        call.return_value={'message':{'content':json.dumps(metadata)}}
        proposals=analyze_photo(photo,self.schema,'local')
        self.assertTrue(all(item['value'] is None for item in proposals))
        payload=call.call_args.args[1]
        encoded=payload['messages'][1]['images'][0]
        self.assertTrue(__import__('base64').b64decode(encoded).startswith(b'\xff\xd8'))
        self.assertFalse(payload['stream'])
        self.assertFalse(payload['think'])
        self.assertEqual(payload['format']['type'],'object')
        vision.assert_called_once_with('local')
        photo.analysis_signature=''
        photo.save(update_fields=['analysis_signature'])
        call.return_value={'message':{'content':'not json'}}
        with self.assertRaises(ValueError):
            analyze_photo(photo,self.schema,'local')

    @patch('core.photo_service.analyze_photo')
    def test_worker_failure_retry_restart_no_duplicate_drafts(self,analyze):
        from .models import PhotoJob
        from .photo_queue import process_next
        photo=self.upload()
        job=PhotoJob.objects.create(checklist=self.survey,requested_by=self.user,model='local',schema=deepcopy(self.schema),baseline={},total=1)
        job.photos.add(photo)
        analyze.side_effect=ValueError('sensitive model output')
        self.assertTrue(process_next())
        job.refresh_from_db()
        self.assertEqual(job.status,'failed')
        self.assertNotIn('sensitive',job.error)
        self.assertEqual(self.reviewer_json(f'jobs/{job.pk}/retry/').status_code,200)
        analyze.side_effect=None
        analyze.return_value=self.proposal()['drafts']
        self.assertTrue(process_next())
        job.refresh_from_db()
        self.assertEqual(job.status,'completed')
        self.assertEqual(job.completed,1)
        self.assertEqual(job.drafts.count(),1)
        job.status='running'
        job.save()
        self.assertTrue(process_next())
        self.assertEqual(job.drafts.count(),1)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{})

    def test_final_survey_blocks_every_write_with_conflict(self):
        job,draft=self.draft()
        self.survey.status=Checklist.Status.FINAL
        self.survey.save()
        for path in ['upload/','enqueue/',f'jobs/{job.pk}/retry/',f'drafts/{draft.pk}/accept/']:
            self.assertEqual(self.post_json(path).status_code,403)
            self.assertEqual(self.reviewer_json(path).status_code,409)

    def test_inference_lease_prevents_parallel_consumers(self):
        from .photo_queue import inference_lease
        from .local_ai import InferenceBusy
        with inference_lease() as check:
            check()
            with self.assertRaises(InferenceBusy):
                with inference_lease():
                    self.fail('Second worker entered held lease')

    def test_available_exif_time_preserved(self):
        stream=BytesIO()
        exif=Image.Exif()
        exif[36867]='2026:10:17 12:34:56'
        Image.new('RGB',(90,60),'blue').save(stream,format='JPEG',exif=exif)
        metadata=prepare_image(SimpleUploadedFile('exif.jpg',stream.getvalue()))[3]
        self.assertEqual(metadata['captured_at'],'2026:10:17 12:34:56')

    @patch('core.photo_service.ollama')
    @patch('core.photo_service.verify_vision')
    def test_lost_lease_after_single_vision_call_prevents_metadata_cache(self, vision, call):
        from .photo_service import analyze_photo
        photo=self.upload()
        call.return_value={'message':{'content':json.dumps({'caption':'An antenna stands above a concrete foundation.','objects':['antenna'],'visible_text':[],'issues':[],'uncertainties':[]})}}
        checks=0
        def check():
            nonlocal checks
            checks+=1
            if checks==3:
                raise RuntimeError('Lease lost after first inference')
        with self.assertRaises(RuntimeError):
            analyze_photo(photo,self.schema,'local',lease_check=check)
        self.assertEqual(call.call_count,1)
        vision.assert_called_once_with('local')
        photo.refresh_from_db()
        self.assertEqual(photo.analysis_signature,'')
        self.assertEqual(photo.analysis_metadata,{})
