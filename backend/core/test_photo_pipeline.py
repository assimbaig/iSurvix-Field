"""Independent photo endpoint, durable stage recovery and embedding reuse."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from . import test_evidence_pipeline as fixtures
from .evidence_learning import digest
from .photo_models import PhotoObservation, PhotoJob, PhotoPlacement
from . import evidence_pipeline as pipeline


class ObservationStageTests(TestCase):
    person=fixtures.EvidencePipelineTests.person
    setUp=fixtures.EvidencePipelineTests.setUp
    pin=fixtures.EvidencePipelineTests.pin
    def observation(self):
        return {'caption':'A concrete foundation supports a lattice tower.',
                'objects':['foundation','tower'],'visible_text':[], 'issues':[], 'uncertainties':[]}

    def prepare(self):
        with patch.object(pipeline,'model_fingerprint',return_value='a'*64), patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            return pipeline.prepare_observation(self.photo,'synthetic-model',self.context,lambda:None)

    def test_durable_observation_reused_after_matching_failure_and_restart(self):
        with patch('core.photo_metadata.extract_metadata',return_value=self.observation()) as native:
            self.assertEqual(self.prepare(),self.observation())
            self.photo.refresh_from_db()
            with patch('core.local_evidence_tools.extract_local_tools',side_effect=ValueError('Synthetic OCR failure')):
                with self.assertRaises(ValueError):
                    with patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
                        pipeline.analyze(self.photo,self.checklist.schema_snapshot,'synthetic-model',self.context,lambda:None,None)
            self.photo.refresh_from_db()
            self.assertEqual(self.prepare(),self.observation())
            native.assert_called_once()
        self.assertEqual(PhotoObservation.objects.count(),1)
        self.assertEqual(PhotoPlacement.objects.count(),0)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.answer_data,{})
        self.assertEqual(self.checklist.section_approvals,{})

    def test_model_digest_change_requires_fresh_observation(self):
        with patch('core.photo_metadata.extract_metadata',return_value=self.observation()) as native:
            self.prepare()
            self.context={**self.context,'model_digest':'c'*64}
            with patch.object(pipeline,'model_fingerprint',return_value='c'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
                pipeline.prepare_observation(self.photo,'synthetic-model',self.context,lambda:None)
            self.assertEqual(native.call_count,2)
        self.assertEqual(PhotoObservation.objects.count(),2)

    def test_cache_integrity_original_bytes_and_lease_are_checked(self):
        with patch('core.photo_metadata.extract_metadata',return_value=self.observation()):
            self.prepare()
        with self.assertRaises(ValidationError):
            PhotoObservation.objects.all().update(payload={})
        with patch.object(self.photo.original,'open') as source:
            from io import BytesIO
            source.return_value=BytesIO(b'tampered synthetic photo')
            with self.assertRaises(ValidationError): self.prepare()
        def lost():raise RuntimeError('Lost lease')
        with self.assertRaises(RuntimeError):
            pipeline.prepare_observation(self.photo,'synthetic-model',self.context,lost)
        self.assertEqual(PhotoObservation.objects.count(),1)

    def test_staged_worker_resumes_without_duplicate_results(self):
        from .photo_queue import process_next
        job=self.pin();job.total=1;job.save(update_fields=['total']);job.photos.add(self.photo)
        with ExitStack() as stack:
            stack.enter_context(patch('core.photo_queue.time.monotonic',return_value=1))
            stack.enter_context(patch('core.evidence_pipeline.prepare_observation',return_value=self.observation()))
            work=stack.enter_context(patch('core.photo_service.analyze_photo',side_effect=ValueError('Synthetic matching failure')))
            process_next();job.refresh_from_db()
            self.assertEqual(job.status,'failed')
            self.assertEqual(job.progress['analysis_ready_photo_ids'],[self.photo.pk])
            self.assertEqual(job.completed,0)
            job.status='queued';job.save(update_fields=['status'])
            work.side_effect=None;work.return_value=[]
            process_next();job.refresh_from_db()
        self.assertEqual(job.status,'completed')
        self.assertEqual(job.processed_photo_ids,[self.photo.pk])
        self.assertEqual(job.progress['pipeline'],'dedicated-photo-v1')


class PhotoEndpointTests(SimpleTestCase):
    def test_ungrounded_supported_claim_becomes_insufficient_without_weakening_validator(self):
        from .evidence_rules import validate_targeted_assessments
        raw={'assessments':[{'field_id':'tower','outcome':'supported','reason':'Claimed support',
                            'visible_evidence':'','missing_evidence':[]}]}
        with self.assertRaises(ValueError):validate_targeted_assessments(raw,{'tower'})
        pipeline.withhold_ungrounded_claims(raw)
        safe=validate_targeted_assessments(raw,{'tower'})
        self.assertEqual(safe[0]['outcome'],'insufficient')
        self.assertIn('withheld',safe[0]['reason'])
        self.assertTrue(safe[0]['missing_evidence'])
        for change in [{'answer':'Checked'},{'field_id':'foreign'},{'missing_evidence':['x']*7},{'reason':None},{'reason':'x'*1601}]:
            invalid={'assessments':[{**raw['assessments'][0],'outcome':'supported','visible_evidence':'',**change}]}
            pipeline.withhold_ungrounded_claims(invalid)
            with self.assertRaises(ValueError):validate_targeted_assessments(invalid,{'tower'})

    @override_settings(OLLAMA_BASE_URL='http://127.0.0.1:11434',PHOTO_OLLAMA_BASE_URL='http://127.0.0.1:11435')
    def test_photo_transport_and_model_identity_use_dedicated_endpoint(self):
        from . import photo_service
        with patch('core.photo_service.assistant_ollama',return_value={'models':[{'name':'synthetic-model','digest':'a'*64}]}) as native:
            self.assertEqual(pipeline.model_fingerprint('synthetic-model'),'a'*64)
            native.assert_called_once_with('/api/tags',None,base_url='http://127.0.0.1:11435')

    @override_settings(OLLAMA_BASE_URL='http://127.0.0.1:11434',PHOTO_OLLAMA_BASE_URL='https://external.invalid')
    def test_photo_transport_still_rejects_non_loopback_addresses(self):
        from .photo_service import ollama
        with self.assertRaises(ValueError):ollama('/api/tags')

    def test_embedding_catalog_texts_are_reused_without_aliasing_vectors(self):
        pipeline._embedding_vectors.clear()
        self.addCleanup(pipeline._embedding_vectors.clear)
        class Vector:
            def tolist(self):return [1.,2.]
        engine=SimpleNamespace(embed=lambda texts:[Vector() for _ in texts])
        with patch.object(pipeline,'embedding_engine',return_value=engine),patch.object(engine,'embed',wraps=engine.embed) as native:
            first=pipeline.embed(['Checklist point','Photo one'])
            first[0][0]=99
            second=pipeline.embed(['Checklist point','Photo two'])
            self.assertEqual(second[0],[1.,2.])
            self.assertEqual(native.call_args_list[1].args[0],['Photo two'])
            pipeline._embedding_vectors.update({str(i):[1.,2.] for i in range(4096)})
            self.assertEqual(pipeline.embed(['Checklist point','New photo'])[0],[1.,2.])


class PhotoLeaseTests(TestCase):
    @override_settings(OLLAMA_BASE_URL='http://127.0.0.1:11434',PHOTO_OLLAMA_BASE_URL='http://127.0.0.1:11435')
    def test_queue_owner_is_exclusive_even_across_different_endpoints(self):
        from .photo_queue import photo_worker_lease
        from .local_ai import InferenceBusy
        with photo_worker_lease() as check:
            check()
            with override_settings(PHOTO_OLLAMA_BASE_URL='http://127.0.0.1:11434'):
                with self.assertRaises(InferenceBusy):
                    with photo_worker_lease():pass

    @override_settings(OLLAMA_BASE_URL='http://127.0.0.1:11434',PHOTO_OLLAMA_BASE_URL='http://127.0.0.1:11435')
    def test_separate_runtime_does_not_hold_chat_lease(self):
        from .photo_queue import inference_lease,photo_inference_lease
        from .local_ai import InferenceBusy
        with inference_lease() as chat,photo_inference_lease() as photos:
            chat();photos()
            with self.assertRaises(InferenceBusy):
                with photo_inference_lease():pass

    @override_settings(OLLAMA_BASE_URL='http://127.0.0.1:11434',PHOTO_OLLAMA_BASE_URL='http://localhost:11434/')
    def test_same_endpoint_preserves_chat_photo_serialization(self):
        from .photo_queue import inference_lease,photo_inference_lease
        from .local_ai import InferenceBusy
        with inference_lease():
            with self.assertRaises(InferenceBusy):
                with photo_inference_lease():pass
