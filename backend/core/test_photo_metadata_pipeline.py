"""Independent metadata-first photo processing and 500-photo bound regressions."""
import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.urls import reverse
from PIL import Image
from .models import Checklist,ChecklistTemplate,Project,Profile,PhotoEvidence,PhotoJob


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class Photo500LimitTests(TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='metadata-qa-',dir=Path(__file__).resolve().parents[2]/'.local')
        self.addCleanup(temporary.cleanup)
        storage=override_settings(MEDIA_ROOT=temporary.name)
        storage.enable()
        self.addCleanup(storage.disable)
        schema={'title':'Metadata fixture','sections':[{'id':'general','title':'General','fields':[{'id':'overview','label':'Site overview','type':'photo'}]}]}
        template=ChecklistTemplate.objects.create(name='Metadata fixture',definition=schema,published=True)
        self.project=Project.objects.create(name='Metadata fixture',checklist_template=template)
        self.user=User.objects.create_user('metadata_engineer')
        self.user.profile.role=Profile.Roles.ENGINEER
        self.user.profile.project=self.project
        self.user.profile.save()
        self.survey=Checklist.objects.create(project=self.project,user=self.user,site_id='SYNTHETIC-METADATA')
        self.client.force_login(self.user)

    def image(self,color='red'):
        data=BytesIO()
        Image.new('RGB',(20,20),color).save(data,format='PNG')
        return SimpleUploadedFile('synthetic.png',data.getvalue(),content_type='image/png')

    def seed(self,survey,count,prefix):
        PhotoEvidence.objects.bulk_create([PhotoEvidence(checklist=survey,filename=f'{prefix}-{index}.png',sha256=f'{prefix}-{index}') for index in range(count)])

    def test_site_accepts_500th_photo_and_refuses_501st_across_checklists(self):
        sibling=Checklist.objects.create(project=self.project,user=self.user,site_id=self.survey.site_id)
        self.seed(sibling,200,'sibling')
        self.seed(self.survey,299,'current')
        url=reverse('photo_upload',args=[self.survey.pk])
        response=self.client.post(url,{'files':[self.image()],'group':'Civil'})
        self.assertEqual(response.status_code,201,response.content)
        response=self.client.post(url,{'files':[self.image('blue')],'group':'Civil'})
        self.assertIn(response.status_code,(400,409))
        self.assertEqual(PhotoEvidence.objects.filter(checklist__project=self.project,checklist__site_id=self.survey.site_id).count(),500)
        # Exact duplicate remains safe/idempotent even when the quota is full.
        response=self.client.post(url,{'files':[self.image()],'group':'Civil'})
        self.assertEqual(response.status_code,201)
        self.assertTrue(response.json()['photos'][0]['duplicate'])

    @patch('core.evidence_pipeline.processing_context',return_value={'rules_version':'synthetic-rules','model_version':'synthetic-local','tool_version':'synthetic-tools','prompt_version':'synthetic-prompt'})
    @patch('core.photo_views.verify_vision')
    def test_enqueue_500_distinct_photos_and_reject_501_without_an_extra_job(self,vision,processing):
        reviewer=User.objects.create_user('metadata_lead')
        reviewer.profile.role=Profile.Roles.TEAM_LEAD
        reviewer.profile.project=self.project
        reviewer.profile.save()
        self.client.force_login(reviewer)
        self.seed(self.survey,501,'queue')
        ids=list(self.survey.photo_evidence.order_by('pk').values_list('pk',flat=True))
        url=reverse('photo_enqueue',args=[self.survey.pk])
        response=self.client.post(url,json.dumps({'photo_ids':ids[:500],'model':'synthetic-local'}),content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        job=PhotoJob.objects.get(pk=response.json()['id'])
        self.assertEqual(job.total,500)
        self.assertEqual(job.photos.count(),500)
        response=self.client.post(url,json.dumps({'photo_ids':ids,'model':'synthetic-local'}),content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(PhotoJob.objects.count(),1)
        vision.assert_called_once_with('synthetic-local')

def compact_observation():
    return {'caption':'An antenna is mounted above a square concrete foundation.','objects':['antenna','concrete foundation'],'visible_text':[],'issues':[],'uncertainties':['No measurements can be established.']}


@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MetadataPipelineTests(TestCase):
    image=Photo500LimitTests.image
    def setUp(self):
        Photo500LimitTests.setUp(self)
        from django.core.files.base import ContentFile
        self.photo=PhotoEvidence.objects.create(checklist=self.survey,filename='synthetic.png',sha256='a'*64)
        self.photo.preview.save('synthetic-preview.png',ContentFile(self.image().read()))

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_one_image_call_for_full_catalog_then_persisted_cache_and_schema_rematch(self,native,vision):
        from .photo_service import analyze_photo
        from .template_service import default_definition
        native.return_value={'message':{'content':json.dumps(compact_observation())}}
        schema=default_definition()
        proposals=analyze_photo(self.photo,schema,'synthetic-model')
        self.assertTrue(all(item['value'] is None for item in proposals))
        native.assert_called_once()
        payload=native.call_args.args[1]
        self.assertEqual(len(payload['messages'][1]['images']),1)
        self.assertNotIn('fields',payload['messages'][1]['content'])
        # Detailed verification has a bounded recovery budget; fast retrieval
        # runs separately and never waits for this autoregressive response.
        self.assertLessEqual(payload['options']['num_predict'],768)
        self.photo=PhotoEvidence.objects.get(pk=self.photo.pk)
        self.assertTrue(self.photo.analysis_signature)
        self.assertEqual(self.photo.analysis_metadata,compact_observation())
        changed={'sections':[{'id':'other','title':'Other','fields':[{'id':'antenna_detail','label':'Antenna photo','type':'photo'}]}]}
        remapped=analyze_photo(self.photo,changed,'synthetic-model')
        self.assertEqual([p['field_id'] for p in remapped],['antenna_detail'])
        self.assertIsNone(remapped[0]['value'])
        self.assertEqual(native.call_count,1)
        self.assertEqual(vision.call_count,1)

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_model_hash_and_prompt_version_each_invalidate_cached_observation(self,native,vision):
        from .photo_metadata import extract_metadata
        native.return_value={'message':{'content':json.dumps(compact_observation())}}
        extract_metadata(self.photo,'model-a')
        first=self.photo.analysis_signature
        extract_metadata(self.photo,'model-b')
        second=self.photo.analysis_signature
        self.assertNotEqual(first,second)
        self.photo.sha256='b'*64
        self.photo.save(update_fields=['sha256'])
        extract_metadata(self.photo,'model-b')
        third=self.photo.analysis_signature
        self.assertNotEqual(second,third)
        with patch('core.photo_metadata.METADATA_VERSION','qa-new-prompt-version'):
            extract_metadata(self.photo,'model-b')
        self.assertNotEqual(third,self.photo.analysis_signature)
        self.assertEqual(native.call_count,4)

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_invalid_metadata_not_cached_and_retry_can_extract_safely(self,native,vision):
        from .photo_metadata import extract_metadata
        from .photo_service import PhotoProcessingError
        native.return_value={'message':{'content':json.dumps({**compact_observation(),'objects':[None]})}}
        with self.assertRaises(PhotoProcessingError):
            extract_metadata(self.photo,'synthetic-model')
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.analysis_metadata,{})
        self.assertEqual(self.photo.analysis_signature,'')
        native.return_value={'message':{'content':json.dumps(compact_observation())}}
        extract_metadata(self.photo,'synthetic-model')
        self.assertEqual(native.call_count,2)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.analysis_metadata,compact_observation())
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{})
        self.assertEqual(self.survey.section_approvals,{})

    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_lost_lease_after_vision_does_not_cache_observations(self,native,vision):
        from .photo_metadata import extract_metadata
        native.return_value={'message':{'content':json.dumps(compact_observation())}}
        checks=0
        def lease():
            nonlocal checks
            checks+=1
            if checks==3:
                raise RuntimeError('Lease lost after native response')
        with self.assertRaises(RuntimeError):
            extract_metadata(self.photo,'synthetic-model',lease_check=lease)
        native.assert_called_once()
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.analysis_metadata,{})
        self.assertEqual(self.photo.analysis_signature,'')

    def test_matching_never_uses_group_section_negatives_or_generic_subjects_as_proof(self):
        from .photo_metadata import match_metadata
        schema={'sections':[{'id':'tower','title':'Tower antenna','fields':[{'id':'antenna','label':'Antenna photo','type':'photo'},{'id':'cabinet','label':'Cabinet panel cable photo','type':'photo'},{'id':'blue_circle','label':'Blue circle','type':'photo'},{'id':'height','label':'Antenna height','type':'number'},{'id':'system','label':'Antenna identity','type':'text','system':'site_id'}]}]}
        metadata={'caption':'A red rectangle stands against a white background; no antenna is visible.','objects':['red rectangle','white background','cabinet'],'visible_text':[],'issues':[],'uncertainties':[]}
        self.assertEqual(match_metadata(metadata,schema),[])
        # An explicit negative must override a contradictory model object-list entry.
        metadata={'caption':'No antenna is visible in the image.','objects':['antenna'],'visible_text':[],'issues':[],'uncertainties':[]}
        self.assertEqual(match_metadata(metadata,schema),[])

    def test_strict_validation_rejects_unsafe_matching_output(self):
        from .photo_service import analyze_photo,PhotoProcessingError
        raw={'field_id':'overview','value':'Unsafe automatic answer','reason':'Observed structures match this requested overview.','visual_evidence':'A square concrete base is visible below the support.','evidence_match':'visible','uncertainty':'high','missing_information':'','anomalies':[]}
        with patch('core.photo_metadata.extract_metadata',return_value=compact_observation()),patch('core.photo_metadata.match_metadata',return_value=[raw]):
            with self.assertRaises(PhotoProcessingError):
                analyze_photo(self.photo,self.survey.schema_snapshot,'synthetic-model')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{})

    def test_rematch_supersedes_only_obsolete_ai_proposals_and_preserves_human_decisions(self):
        from .models import PhotoPlacement
        from .field_photo_service import record_proposals,schema_digest
        fields=[{'id':fid,'label':fid,'type':'photo'} for fid in ['overview','obsolete','confirmed','manual','rejected']]
        schema={'title':'Supersession fixture','sections':[{'id':'general','title':'General','fields':fields}]}
        self.survey.schema_snapshot=schema
        self.survey.save(update_fields=['schema_snapshot'])
        job=PhotoJob.objects.create(checklist=self.survey,requested_by=self.user,model='synthetic-model',schema=schema)
        original={}
        for fid,status in [('overview','proposed'),('obsolete','proposed'),('confirmed','confirmed'),('manual','manual'),('rejected','rejected')]:
            item=PhotoPlacement.objects.create(photo=self.photo,job=job,field_id=fid,section_id='general',status=status,reason='Preserved original decision',schema_digest=schema_digest(self.survey),reviewed_by=self.user if status!='proposed' else None)
            original[fid]=item.pk
        proposal={'field_id':'overview','value':None,'evidence_match':'visible','visual_evidence':'An antenna is mounted above a square concrete foundation.','reason':'The visible antenna and concrete foundation match this requested overview.','uncertainty':'high'}
        record_proposals(job,self.photo,[proposal])
        states=dict(PhotoPlacement.objects.filter(photo=self.photo).values_list('field_id','status'))
        self.assertEqual(states,{'overview':'proposed','obsolete':'superseded','confirmed':'confirmed','manual':'manual','rejected':'rejected'})
        self.assertEqual(dict(PhotoPlacement.objects.filter(photo=self.photo).values_list('field_id','pk')),original)
        obsolete=PhotoPlacement.objects.get(pk=original['obsolete'])
        self.assertIsNone(obsolete.reviewed_by)
        self.assertEqual(obsolete.reason,'Preserved original decision')
        for fid in ['confirmed','manual','rejected']:
            item=PhotoPlacement.objects.get(pk=original[fid])
            self.assertEqual(item.reviewed_by,self.user)
            self.assertEqual(item.reason,'Preserved original decision')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.answer_data,{})
        self.assertEqual(self.survey.section_approvals,{})
