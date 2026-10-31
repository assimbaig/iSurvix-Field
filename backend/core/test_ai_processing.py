"""Provider routing regressions use disposable records and controlled transports."""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from .models import Company, Project, Checklist, Profile, IndustryCatalog
from .survey_processing_models import SurveyProcessingRevision, SurveyProcessingJob


class AIProcessingTests(TestCase):
    def setUp(self):
        self.company=Company.objects.create(name='AI synthetic tenant')
        self.admin=User.objects.create_user('ai-config-admin')
        self.admin.profile.role=Profile.Roles.ADMIN
        self.admin.profile.company=self.company
        self.admin.profile.admin_industry=IndustryCatalog.objects.create(code='ai-test',name='AI test')
        self.admin.profile.save()
        project=Project.objects.create(name='AI test',company=self.company,administrator=self.admin)
        c=Checklist.objects.create(project=project,user=self.admin,site_id='SYNTHETIC-AI')
        self.revision=SurveyProcessingRevision.objects.create(checklist=c,number=1,digest='a'*64,snapshot={},submitted_by=self.admin)
        self.job=SurveyProcessingJob.objects.create(revision=self.revision,model='qwen3.5:4b')

    def configure(self,**changes):
        from .ai_processing_service import update_settings
        return update_settings(self.admin,self.company,{'enabled':True,**changes},expected_version=0)

    def test_completed_request_replayed_without_inference_or_quota_charge(self):
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingRequest, AIProcessingQuota
        self.configure()
        callback=lambda provider:{'valid':'evidence','provider':provider.kind}
        result=execute_request(self.job,'photo:1',{'sha':'a'},callback)
        with patch('core.ai_processing_service.provider_for',side_effect=AssertionError('duplicate inference')):
            self.assertEqual(execute_request(self.job,'photo:1',{'sha':'a'},callback),result)
        self.assertEqual(AIProcessingRequest.objects.count(),1)
        self.assertEqual(AIProcessingQuota.objects.get().used,1)

    def test_zero_quota_blocks_before_provider(self):
        from .ai_processing_service import execute_request
        self.configure(daily_request_limit=0)
        with patch('core.ai_processing_service.provider_for') as provider:
            with self.assertRaisesMessage(ValidationError,'quota'):
                execute_request(self.job,'photo:1',{},lambda p:{'ok':True})
            provider.assert_not_called()

    def test_foreign_admin_cannot_update_and_secret_payload_rejected(self):
        from .ai_processing_service import update_settings
        foreign=Company.objects.create(name='Another tenant')
        with self.assertRaises(PermissionDenied):update_settings(self.admin,foreign,{},expected_version=0)
        with self.assertRaises(ValidationError):self.configure(api_key='never-persist-this')

    def test_timeout_fallback_recorded_and_result_not_approved(self):
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingAttempt
        registry={'synthetic':{'endpoint':'https://model.example.test','credential_env':'TEST_PROVIDER_KEY'}}
        with override_settings(AI_PROVIDER_REGISTRY=registry):
            self.configure(primary_provider='local',fallback_enabled=True,allow_external_evidence=True,api_endpoint='synthetic',api_model='vision-test')
            def callback(provider):
                if provider.kind=='local':raise TimeoutError('private transport details')
                return {'findings':[],'verification_status':'needs_review'}
            result=execute_request(self.job,'photo:1',{},callback)
        self.assertEqual(result['verification_status'],'needs_review')
        self.assertEqual(list(AIProcessingAttempt.objects.values_list('provider','outcome')), [('local','failed'),('https_ollama','succeeded')])
        self.assertNotIn('private transport',str(list(AIProcessingAttempt.objects.values())))

    def test_settings_stale_version_and_unapproved_external_processing_rejected(self):
        from .ai_processing_service import update_settings
        self.configure()
        with self.assertRaises(ValidationError):update_settings(self.admin,self.company,{'enabled':True},expected_version=0)
        with self.assertRaises(ValidationError):update_settings(self.admin,self.company,{'primary_provider':'https_ollama'},expected_version=1)

    def test_local_transport_uses_company_timeout(self):
        from .ai_providers import Provider
        provider=Provider('local','qwen3.5:4b',{'request_timeout':37})
        with patch('core.local_ai.ollama',return_value={}) as transport:
            provider.request('/api/chat',{'model':provider.model})
        self.assertEqual(transport.call_args.kwargs.get('timeout'),37)

    def test_expired_attempt_receipt_is_marked_abandoned(self):
        from datetime import timedelta
        from django.utils import timezone
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingRequest,AIProcessingAttempt
        self.configure()
        def late(provider):
            AIProcessingRequest.objects.update(lease_until=timezone.now()-timedelta(seconds=1))
            return {'late':'result'}
        with self.assertRaises(ValidationError):execute_request(self.job,'photo:1',{},late)
        self.assertEqual(AIProcessingAttempt.objects.get().outcome,'abandoned')

    def test_bounded_retry_and_quota_include_failures(self):
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingQuota,AIProcessingAttempt
        self.configure()
        for _ in range(4):
            with self.assertRaises(ValidationError):
                execute_request(self.job,'photo:1',{},lambda p: (_ for _ in ()).throw(TimeoutError('private-error')))
        with self.assertRaisesMessage(ValidationError,'retry limit'):
            execute_request(self.job,'photo:1',{},lambda p:self.fail('fifth request must never execute'))
        self.assertEqual(AIProcessingQuota.objects.get().used,4)
        self.assertEqual(AIProcessingAttempt.objects.count(),4)

    def test_active_source_is_not_processed_twice(self):
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingQuota
        self.configure()
        def concurrent(provider):
            with self.assertRaisesMessage(ValidationError,'already processing'):
                execute_request(self.job,'photo:1',{},lambda p:self.fail('duplicate callback'))
            return {'valid':True}
        execute_request(self.job,'photo:1',{},concurrent)
        self.assertEqual(AIProcessingQuota.objects.get().used,1)

    def test_late_old_attempt_cannot_change_a_new_workers_receipt(self):
        from datetime import timedelta
        from django.utils import timezone
        from .ai_processing_service import execute_request
        from .ai_processing_models import AIProcessingRequest,AIProcessingAttempt
        self.configure()
        def old(provider):
            AIProcessingRequest.objects.update(lease_until=timezone.now()-timedelta(seconds=1))
            execute_request(self.job,'photo:1',{},lambda p:{'new':'result'})
            return {'old':'result'}
        with self.assertRaises(ValidationError):execute_request(self.job,'photo:1',{},old)
        saved=AIProcessingRequest.objects.get()
        self.assertEqual(saved.result,{'new':'result'})
        self.assertEqual(list(AIProcessingAttempt.objects.values_list('outcome',flat=True)),['abandoned','succeeded'])

    def test_api_registry_change_after_policy_pin_is_rejected_before_delivery(self):
        from .ai_processing_service import execute_request,policy_for
        from .ai_providers import provider_for
        with override_settings(AI_PROVIDER_REGISTRY={'fixture':{'endpoint':'https://first.example.test','credential_env':''}}):
            self.configure(primary_provider='https_ollama',api_endpoint='fixture',api_model='fixture-vision',allow_external_evidence=True)
            policy=policy_for(self.job)
        with override_settings(AI_PROVIDER_REGISTRY={'fixture':{'endpoint':'https://changed.example.test','credential_env':''}}):
            provider=provider_for('https_ollama',policy.snapshot)
            with self.assertRaisesMessage(ValidationError,'connection changed'):
                provider.request('/api/tags')

    @override_settings(LOCAL_AI_ENABLED=False)
    def test_configured_worker_keeps_local_only_job_queued(self):
        from .survey_processing import process_next
        self.configure()
        with patch('core.local_ai.ollama',side_effect=AssertionError('hosted worker must not use loopback')):
            self.assertFalse(process_next(configured_providers=True))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'queued')

    @override_settings(LOCAL_AI_ENABLED=False)
    def test_configured_worker_command_runs_without_enabling_local_inference(self):
        from django.core.management import call_command
        with patch('core.management.commands.survey_processing_worker.process_next',return_value=False) as process:
            call_command('survey_processing_worker',configured_providers=True,once=True)
        process.assert_called_once_with(configured_providers=True)


@override_settings(SECRET_KEY='isolated-routing',ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                  AI_PROVIDER_REGISTRY={'fixture':{'endpoint':'https://fixture.example.test','credential_env':''}})
class AIProcessingPipelineTests(TestCase):
    def test_real_job_api_primary_does_not_require_local_model_and_preserves_human_answers(self):
        from contextlib import nullcontext
        from .test_survey_processing import SurveyProcessingTests
        from . import survey_processing
        from .ai_processing_models import AIProcessingSettings,AIProcessingRequest
        fixture=SurveyProcessingTests('runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        AIProcessingSettings.objects.create(company=fixture.company,enabled=True,primary_provider='https_ollama',
            api_endpoint='fixture',api_model='fixture-vision',allow_external_evidence=True)
        revision,_=survey_processing.submit(fixture.request(),fixture.checklist.pk,True)
        from .remote_worker_models import RemoteWorkerProject
        RemoteWorkerProject.objects.create(project=fixture.project,enabled=True)
        before=fixture.pristine()
        captured=[]
        def transport(provider,path,payload=None,**ignored):
            if provider.kind=='local':raise AssertionError('API-primary must not call local Ollama')
            if path=='/api/tags':return {'models':[{'name':'fixture-vision'}]}
            if path=='/api/show':return {'capabilities':['vision']}
            captured.append(payload)
            return {'message':{'content':'{"findings":[],"missing":["No supported readings"],"conflicts":[],"suggested_items":[]}'},'done_reason':'stop'}
        with patch('core.ai_providers.Provider.request',autospec=True,side_effect=transport), \
             patch('core.survey_model_identity.verified_identity',side_effect=AssertionError('local identity forbidden')), \
             patch('core.photo_queue.photo_inference_lease',side_effect=lambda:nullcontext(lambda:None)), \
             patch('core.survey_processing.render_drawing_set'):
            survey_processing.process_next(configured_providers=True)
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'ready_for_review',revision.processing_job.error)
        self.assertEqual(fixture.pristine(),before)
        self.assertGreaterEqual(len(captured),1)
        self.assertTrue(all(message['messages'][1]['images'][0] for message in captured))
        self.assertEqual(AIProcessingRequest.objects.filter(state='succeeded').count(),2)
