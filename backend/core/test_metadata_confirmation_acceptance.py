"""Independent metadata-to-location confirmation contracts; all inference is mocked."""
import json
from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase,override_settings
from . import test_photo_placements as fixtures
from .models import PhotoEvidence,PhotoJob,PhotoPlacement
from .field_photo_service import schema_digest
from .photo_queue import process_next

@override_settings(SECRET_KEY='synthetic-metadata-confirmation-tests',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MetadataConfirmationAcceptanceTests(TestCase):
    setUp=fixtures.PhotoPlacementTests.setUp
    image=fixtures.PhotoPlacementTests.image
    upload=fixtures.PhotoPlacementTests.upload
    mapping=fixtures.PhotoPlacementTests.mapping
    decision=fixtures.PhotoPlacementTests.decision
    def new_job(self,photo):
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='synthetic-vision-model',schema=deepcopy(self.schema),baseline=deepcopy(self.c.answer_data),total=1)
        job.photos.add(photo);return job
    def pristine(self):
        self.c.refresh_from_db()
        return deepcopy((self.c.answer_data,self.c.section_approvals,self.c.client_approval,self.c.review_history))
    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_actual_metadata_worker_proposes_only_until_authorized_reviewer_confirms(self,native,vision):
        # Mock native model/tool boundaries, retaining the real versioned worker,
        # deterministic evidence evaluator, durable records and human confirmation.
        for target,value in [('core.evidence_pipeline.model_fingerprint','a'*64),
                             ('core.evidence_pipeline.tool_fingerprint','b'*64),
                             ('core.local_evidence_tools.extract_local_tools',{}),
                             ('core.local_evidence_tools.semantic_similarities',{}),
                             ('core.evidence_rules.verify_shortlist',[])]:
            self.enterContext(patch(target,return_value=value))
        native.return_value={'message':{'content':json.dumps({'caption':'A square concrete foundation is clearly visible below an upright antenna.','objects':['concrete foundation','antenna'],'visible_text':[],'issues':[],'uncertainties':['Measurements are not visible.']})}}
        photo=self.upload();before=self.pristine()
        self.client.force_login(self.lead)
        with patch('core.photo_views.verify_vision') as enqueue_gate:
            queued=self.client.post(self.base+'enqueue/',json.dumps({'photo_ids':[photo.pk],'model':'synthetic-vision-model'}),content_type='application/json')
            self.assertEqual(queued.status_code,201,queued.content)
            enqueue_gate.assert_called_once_with('synthetic-vision-model')
        job=PhotoJob.objects.get(pk=queued.json()['id'])
        native.assert_not_called()
        self.assertTrue(process_next());job.refresh_from_db();photo.refresh_from_db()
        self.assertEqual(job.status,'completed',job.error);self.assertEqual(job.completed,1)
        native.assert_called_once();vision.assert_called_once()
        self.assertTrue(photo.analysis_metadata);self.assertTrue(photo.analysis_signature)
        proposals=list(PhotoPlacement.objects.filter(photo=photo,status='proposed'))
        self.assertTrue(proposals);self.assertEqual(self.pristine(),before)
        self.assertTrue(all(value is None for value in job.drafts.values_list('value',flat=True)))
        result=self.mapping([self.decision(p) for p in proposals]);self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(PhotoPlacement.objects.filter(photo=photo,status='confirmed').count(),len(proposals))
        self.assertEqual(self.pristine(),before)
        # A fresh durable rerun reuses the observation and never undoes human decisions.
        second=self.new_job(photo);self.assertTrue(process_next());second.refresh_from_db()
        self.assertEqual(second.status,'completed',second.error);self.assertEqual(native.call_count,1)
        self.assertEqual(PhotoPlacement.objects.filter(photo=photo,status='confirmed').count(),len(proposals))
        self.assertEqual(self.pristine(),before)
    def test_human_manual_confirmed_and_rejected_locations_survive_new_matching(self):
        from .field_photo_service import record_proposals
        photo=self.upload();job=self.new_job(photo);digest=schema_digest(self.c)
        statuses={'civil_photo':'manual','condition':'confirmed','tower_photo':'rejected'}
        for fid,status in statuses.items():
            section='tower' if fid=='tower_photo' else 'civil'
            PhotoPlacement.objects.create(photo=photo,field_id=fid,section_id=section,status=status,schema_digest=digest,reviewed_by=self.user)
        before=self.pristine()
        record_proposals(job,photo,[{'field_id':fid,'reason':'Visible concrete foundation inspected against original source.','visual_evidence':'The concrete foundation and upright tower are visible in this source photo.','evidence_match':'visible','uncertainty':'high'} for fid in statuses])
        self.assertEqual(dict(PhotoPlacement.objects.filter(photo=photo).values_list('field_id','status')),statuses)
        self.assertEqual(self.pristine(),before)
    def test_over_100_requires_chunks_and_later_failed_chunk_does_not_undo_confirmed_sources(self):
        digest=schema_digest(self.c);proposals=[]
        for i in range(101):
            photo=PhotoEvidence.objects.create(checklist=self.c,filename=f'synthetic-{i}.png',sha256=f'{i:064x}')
            proposals.append(PhotoPlacement.objects.create(photo=photo,field_id='civil_photo',section_id='civil',status='proposed',schema_digest=digest))
        before=self.pristine()
        too_many=self.mapping([self.decision(p) for p in proposals]);self.assertIn(too_many.status_code,(400,409))
        self.assertEqual(PhotoPlacement.objects.filter(status='confirmed').count(),0)
        first=self.mapping([self.decision(p) for p in proposals[:100]]);self.assertEqual(first.status_code,200,first.content)
        last=self.decision(proposals[-1]);last['mapping_id']=0
        failed=self.mapping([last]);self.assertIn(failed.status_code,(400,409))
        self.assertEqual(PhotoPlacement.objects.filter(status='confirmed').count(),100)
        self.assertEqual(PhotoPlacement.objects.filter(status='proposed').count(),1)
        self.assertEqual(self.pristine(),before)
