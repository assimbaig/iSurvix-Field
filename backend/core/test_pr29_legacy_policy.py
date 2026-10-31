"""Enabling company routing cannot replace an interrupted native model pin."""
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase,override_settings
from .ai_processing_models import AIProcessingSettings,AIProcessingPolicy
from . import ai_processing_service, survey_processing
from .remote_worker_models import RemoteWorkerProject
from .test_remote_survey_worker import Fixtures,SETTINGS


@override_settings(SECRET_KEY='isolated-pr29-review',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                  AI_PROVIDER_REGISTRY={'approved-fixture':{'endpoint':'https://provider.example.test','credential_env':'TEST_PROVIDER_TOKEN'}})
class LegacyLocalPolicyTests(TestCase):
    def setUp(self):
        from .test_survey_processing import SurveyProcessingTests
        self.fixture=SurveyProcessingTests('runTest')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.revision,_=survey_processing.submit(self.fixture.request(),self.fixture.checklist.pk,True)
        self.job=self.revision.processing_job

    def enable_api(self):
        return AIProcessingSettings.objects.create(company=self.fixture.company,enabled=True,
            primary_provider='https_ollama',api_endpoint='approved-fixture',api_model='fixture-vision',allow_external_evidence=True)

    def native_pin(self):
        self.job.model_digest='d'*64
        self.job.save(update_fields=['model_digest'])

    def test_completed_native_checkpoint_resumes_without_repeating_or_repinning(self):
        calls=[]
        def interrupted(source,model,*args,**kwargs):
            calls.append(source['source_id'])
            if len(calls)>1:raise TimeoutError('synthetic interruption')
            return self.fixture.analysed(source,model)
        self.fixture.processing(analyse=interrupted)
        survey_processing.process_next()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'failed')
        self.assertEqual(self.job.completed,1)
        native_pin=self.job.model_digest
        checkpoint=self.revision.source_analyses.get()
        preserved=(checkpoint.pk,checkpoint.source_id,checkpoint.digest,checkpoint.payload)
        self.enable_api()
        survey_processing.retry(self.fixture.request(),self.fixture.checklist.pk,self.revision.pk)
        _,analysis,_=self.fixture.processing()
        survey_processing.process_next()
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'ready_for_review',self.job.error)
        self.assertEqual(self.job.model_digest,native_pin)
        self.assertEqual(analysis.call_count,1,'Only the unfinished photo may be analysed.')
        checkpoint.refresh_from_db()
        self.assertEqual((checkpoint.pk,checkpoint.source_id,checkpoint.digest,checkpoint.payload),preserved)
        self.assertFalse(AIProcessingPolicy.objects.filter(job=self.job).exists())

    def test_api_only_worker_leaves_native_pinned_job_for_original_worker(self):
        self.native_pin();self.enable_api()
        with patch('core.local_ai.ollama',side_effect=AssertionError('No native model call from API-only worker')):
            self.assertFalse(survey_processing.process_next(configured_providers=True))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'queued')
        self.assertEqual(self.job.attempts,0)

    def test_local_worker_does_not_steal_legacy_remote_pinned_job(self):
        self.native_pin();self.enable_api()
        RemoteWorkerProject.objects.create(project=self.fixture.project,enabled=True)
        self.assertIsNone(survey_processing.claim())
        self.job.refresh_from_db()
        self.assertEqual(self.job.attempts,0)

    def test_stale_unpinned_object_cannot_create_policy_after_native_pin_is_saved(self):
        stale_job=type(self.job).objects.get(pk=self.job.pk)
        self.native_pin();self.enable_api()
        with self.assertRaisesMessage(ValidationError,'native model'):
            ai_processing_service.policy_for(stale_job)
        self.assertFalse(AIProcessingPolicy.objects.filter(job=self.job).exists())

    def test_unpinned_new_job_still_selects_new_company_policy(self):
        self.enable_api()
        self.assertTrue(ai_processing_service.configured(self.job))
        policy=ai_processing_service.policy_for(self.job)
        self.assertEqual(policy.snapshot['primary_provider'],'https_ollama')

    def test_existing_incompatible_policy_is_preserved_instead_of_deleting_pin(self):
        self.enable_api()
        policy=ai_processing_service.policy_for(self.job)
        self.native_pin()
        policy_bytes=(policy.pk,policy.fingerprint,policy.snapshot)
        with self.assertRaisesMessage(ValidationError,'already has another model'):
            ai_processing_service.pin_processing_identity(self.job,ai_processing_service.processing_identity(self.job))
        policy.refresh_from_db();self.job.refresh_from_db()
        self.assertEqual((policy.pk,policy.fingerprint,policy.snapshot),policy_bytes)
        self.assertEqual(self.job.model_digest,'d'*64)

    @override_settings(OLLAMA_TIMEOUT=180)
    def test_legacy_lease_budget_does_not_change_with_new_company_timeout(self):
        self.native_pin()
        config=self.enable_api();config.request_timeout=600;config.save()
        self.assertEqual(ai_processing_service.lease_seconds(self.job),300)


@override_settings(**SETTINGS)
class LegacyRemotePolicyTests(Fixtures,TestCase):
    def test_pinned_native_worker_can_continue_after_company_configuration_is_enabled(self):
        from . import remote_worker_service as bridge
        claimed=bridge.claim(self.credential,self.identity)
        job=self.revision.processing_job
        job.refresh_from_db()
        native_pin=job.model_digest
        AIProcessingSettings.objects.create(company=self.company,enabled=True)
        task=bridge.next_task(self.credential,claimed['job_id'],claimed['lease'])
        self.assertEqual(task['kind'],'source')
        self.complete(claimed,task)
        job.refresh_from_db()
        self.assertEqual(job.model_digest,native_pin)
        self.assertEqual(self.revision.source_analyses.count(),1)
        self.assertFalse(AIProcessingPolicy.objects.filter(job=job).exists())
