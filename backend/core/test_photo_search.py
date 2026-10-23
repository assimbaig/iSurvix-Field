"""Fast retrieval must never count as completed evidence verification."""
import hashlib
from io import BytesIO
from unittest.mock import patch
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import connection
from django.test import TestCase,override_settings
from django.urls import reverse
from PIL import Image
from . import test_evidence_pipeline as fixtures
from . import photo_search as search
from .photo_models import PhotoEvidence,PhotoJob,PhotoSearchVector,PhotoSearchResult,PhotoPlacement
from .field_photo_service import analysis_state

class FastPhotoSearchTests(TestCase):
    person=fixtures.EvidencePipelineTests.person
    def setUp(self):
        fixtures.EvidencePipelineTests.setUp(self)
        data=BytesIO();Image.new('RGB',(100,80),'blue').save(data,format='PNG')
        self.photo.original.save('fast-synthetic.png',ContentFile(data.getvalue()))
        self.photo.sha256=hashlib.sha256(data.getvalue()).hexdigest();self.photo.save(update_fields=['sha256'])
        self.job=PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,schema=self.checklist.schema_snapshot,model='synthetic',total=1)
        self.job.photos.add(self.photo)
        self.enterContext(patch.object(search,'model_identity',return_value='d'*64))
        # These are queue/cache contracts, not native-model installation tests.
        # Keep the availability probe inside the same disposable fixture as the
        # synthetic encoders so an untracked local model cache is never required.
        models=search.Path(self.media.name)/'models'
        models.mkdir()
        (models/'manifest.json').write_text('{"fixture":"synthetic encoders"}',encoding='utf-8')
        self.enterContext(patch.object(search,'MODELS',models))
        self.enterContext(patch.object(search,'STATE',search.Path(self.media.name)/'worker'))
        self.fields=[{'id':'base','label':'Foundation','section':'General','text':'A foundation'}]
        self.vector=[1.]+[0.]*511
        self.enterContext(patch.object(search,'encoded_catalog',return_value=(self.fields,[self.vector])))
        self.native=SimpleNamespace(embed=lambda images,**kwargs:[self.vector[:] for _ in images])
        self.enterContext(patch.object(search,'encoders',return_value=(self.native,None)))
    def run_batch(self):return search.process_batch(self.job,[self.photo],lambda:None)
    def test_real_stage_writes_only_unverified_candidates_and_keeps_completion_gate(self):
        self.run_batch();result=PhotoSearchResult.objects.get()
        self.assertFalse(result.payload['verification_complete'])
        self.assertEqual(result.payload['candidates'][0]['status'],'unverified')
        self.assertIsNone(result.payload['approval'])
        self.assertEqual(PhotoPlacement.objects.count(),0)
        self.job.refresh_from_db();self.assertEqual(self.job.processed_photo_ids,[])
        self.assertFalse(analysis_state(self.checklist)['review_ready'])
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.answer_data,{})
    def test_completed_index_is_reused_across_workers_and_readers(self):
        self.run_batch()
        with patch.object(self.native,'embed') as encode:
            self.assertFalse(search.process_next());encode.assert_not_called()
        results=[]
        for actor in [self.quality,self.lead]:
            self.client.force_login(actor)
            response=self.client.get(reverse('photo_fast_state',args=[self.checklist.pk]))
            self.assertEqual(response.status_code,200,response.content)
            results.append(response.json()['results'])
        self.assertEqual(results[0],results[1])
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(reverse('photo_fast_state',args=[self.checklist.pk])).status_code,403)
    def test_schema_rematch_reuses_vector_but_not_prior_checklist_ranking(self):
        self.run_batch()
        self.checklist.schema_snapshot['sections'][0]['fields'][0]['label']='Changed subject'
        self.checklist.save(update_fields=['schema_snapshot'])
        self.job.schema=self.checklist.schema_snapshot;self.job.save(update_fields=['schema'])
        with patch.object(self.native,'embed') as encode:
            self.run_batch();encode.assert_not_called()
        self.assertEqual(PhotoSearchVector.objects.count(),1)
        self.assertEqual(PhotoSearchResult.objects.count(),2)
    def test_original_and_cached_payload_tampering_fail_closed(self):
        self.run_batch()
        with connection.cursor() as cursor:
            cursor.execute('UPDATE core_photosearchresult SET payload=%s',['{}'])
        with self.assertRaises(ValidationError):search.state(self.checklist,[self.photo])
        self.photo.original.save('corrupt.png',ContentFile(b'changed bytes'))
        with self.assertRaises(ValidationError):self.run_batch()
    def test_role_revocation_and_lost_lease_write_no_results(self):
        self.engineer.is_active=False;self.engineer.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):self.run_batch()
        self.engineer.is_active=True;self.engineer.save(update_fields=['is_active'])
        def lost():raise RuntimeError('Synthetic lease loss')
        with self.assertRaises(RuntimeError):search.process_batch(self.job,[self.photo],lost)
        self.assertEqual(PhotoSearchResult.objects.count(),0)
    def test_server_paginates_two_results_and_rejects_foreign_activity(self):
        self.run_batch();self.client.force_login(self.quality)
        response=self.client.get(reverse('photo_fast_state',args=[self.checklist.pk])+'?page=999')
        self.assertEqual(len(response.json()['results']),1)
        self.assertEqual(response.json()['page'],1)
        self.assertEqual(self.client.get(reverse('photo_fast_state',args=[999999])).status_code,404)
    def test_invalid_vector_rejected_before_persistence(self):
        for value in [[1.]*511,[float('nan')]*512,[0.]*512]:
            with self.assertRaises(ValidationError):search.normalize(value)
    def test_profile_contact_and_measurement_fields_cannot_be_visual_candidates(self):
        self.checklist.schema_snapshot={'sections':[{'id':'general','title':'General','fields':[
            {'id':'phone','label':'Surveyor mobile number','type':'text'},
            {'id':'height','label':'Tower height','type':'number','photo_required':True},
            {'id':'condition','label':'Foundation condition','type':'inspection'},
            {'id':'sign','label':'Site sign','type':'photo'},
            {'id':'required_note','label':'Cabinet evidence','type':'text','photo_required':True}]}]}
        self.assertEqual([f['id'] for f in search.catalog(self.checklist)],['condition','sign','required_note'])
    def test_fast_site_pass_includes_prior_photos_outside_resumed_deep_job(self):
        data=BytesIO();Image.new('RGB',(90,70),'red').save(data,format='PNG')
        second=PhotoEvidence.objects.create(checklist=self.checklist,filename='other.png',sha256=hashlib.sha256(data.getvalue()).hexdigest())
        second.original.save('other.png',ContentFile(data.getvalue()))
        self.assertEqual(self.job.photos.count(),1)
        self.assertTrue(search.process_next())
        self.assertEqual(PhotoSearchResult.objects.count(),2)
