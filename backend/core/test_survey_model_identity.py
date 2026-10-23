"""Installed model identity and explicit QA recovery, never live inference."""
from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import DatabaseError,connection
from django.test import SimpleTestCase,TestCase,override_settings
from . import test_engineer_category_submission_acceptance as fixture
from . import test_survey_processing as pipeline_fixture
from . import survey_model_identity as identity,survey_processing as pipeline
from .survey_processing_models import SurveySourceAnalysis,SurveyProcessingResult,SurveyDrawingSet


@override_settings(PHOTO_OLLAMA_BASE_URL='http://127.0.0.1:11435',OLLAMA_BASE_URL='http://127.0.0.1:11434')
class InstalledModelIdentityTests(SimpleTestCase):
    def verified(self,manifest='a'*64,path='old-store'):
        with patch('core.photo_service.ollama',side_effect=[
            {'models':[{'name':'qwen3.5:4b','digest':manifest}]},
            {'capabilities':['completion','vision'],'modelfile':'FROM '+path}]) as transport:
            result=identity.verified_identity('qwen3.5:4b',pipeline.PIPELINE_VERSION)
        self.assertTrue(all(call.kwargs['base_url']=='http://127.0.0.1:11435' for call in transport.call_args_list))
        return result

    def test_pin_uses_photo_manifest_not_volatile_store_path_or_text_endpoint(self):
        first=self.verified();second=self.verified(path='repaired-store')
        self.assertEqual(first['fingerprint'],second['fingerprint'])
        self.assertNotEqual(first['legacy_fingerprint'],second['legacy_fingerprint'])
        self.assertNotEqual(first['fingerprint'],self.verified(manifest='b'*64)['fingerprint'])

    def test_missing_manifest_nonvision_and_remote_models_are_not_accepted(self):
        for manifest,details in [('',{'capabilities':['vision']}),('a'*64,{'capabilities':['completion']}),
            ('a'*64,{'capabilities':['vision'],'remote_host':'https://remote.invalid'})]:
            with self.subTest(manifest=manifest,details=details),patch('core.photo_service.ollama',side_effect=[
                {'models':[{'name':'qwen3.5:4b','digest':manifest}]},details]):
                with self.assertRaises((ValueError,ValidationError)):identity.verified_identity('qwen3.5:4b',pipeline.PIPELINE_VERSION)

    def test_existing_photo_transport_forwards_actual_endpoint_and_manifest_reads(self):
        with patch('core.photo_service.assistant_ollama',side_effect=[
            {'models':[{'name':'qwen3.5:4b','digest':'a'*64}]},{'capabilities':['vision']}]) as native:
            result=identity.verified_identity('qwen3.5:4b',pipeline.PIPELINE_VERSION)
        self.assertEqual(result['manifest_digest'],'a'*64)
        self.assertEqual([call.args[0] for call in native.call_args_list],['/api/tags','/api/show'])
        self.assertTrue(all(call.kwargs['base_url']=='http://127.0.0.1:11435' for call in native.call_args_list))


@override_settings(SECRET_KEY='isolated-model-recovery',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAZeroProgressModelRecoveryTests(TestCase):
    setUp=fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person=fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    analysed=fixture.EngineerCategorySubmissionAcceptanceTests.analysed
    processing=fixture.EngineerCategorySubmissionAcceptanceTests.processing
    post=fixture.EngineerCategorySubmissionAcceptanceTests.post
    state=fixture.EngineerCategorySubmissionAcceptanceTests.state
    raw=fixture.EngineerCategorySubmissionAcceptanceTests.raw
    upload=fixture.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixture.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=fixture.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action=fixture.EngineerCategorySubmissionAcceptanceTests.qa_action
    route=fixture.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually=fixture.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def prepare(self):
        self.upload('Civil')
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        self.revision=self.checklist.processing_revisions.get();self.job=self.revision.processing_job
        self.job.model_digest='f'*64;self.job.status='failed';self.job.error=identity.MISMATCH+' Configuration identity changed.'
        self.job.save(update_fields=['model_digest','status','error'])
        self.selected={'version':identity.VERSION,'model':self.job.model,'manifest_digest':'a'*64,
            'fingerprint':'b'*64,'legacy_fingerprint':'c'*64}
        self.before=deepcopy(self.revision.snapshot)
        return self.qa_state()

    def recovery_payload(self,state):
        return {'action':'retry_current_model','revision_id':state['revision_id'],
            'source_digest':state['source_digest'],'expected_review_digest':state['review_digest'],
            'expected_model_digest':state['model_recovery']['expected_model_digest'],
            'reason':'QA explicitly selected the current locally installed model for this unchanged zero-progress submission.'}

    def test_explicit_recovery_is_scoped_audited_idempotent_and_keeps_sources(self):
        state=self.prepare();self.assertTrue(state['model_recovery']['available'])
        payload=self.recovery_payload(state)
        with patch('core.survey_model_identity.verified_identity',return_value=self.selected) as verify:
            first=self.post('photo_capture_review_action',payload)
            second=self.post('photo_capture_review_action',payload)
        self.assertEqual(first.status_code,200,first.content);self.assertEqual(second.status_code,200,second.content)
        self.assertFalse(first.json()['model_recovery']['available'])
        self.assertEqual(verify.call_count,1)
        self.job.refresh_from_db();self.revision.refresh_from_db()
        self.assertEqual((self.job.status,self.job.model_digest),('queued',self.selected['fingerprint']))
        self.assertEqual(self.revision.snapshot,self.before)
        events=self.revision.processing_events.filter(action='qa_model_recovery')
        self.assertEqual(events.count(),1)
        event=events.get();self.assertEqual(event.actor_id,self.quality.pk)
        self.assertEqual(event.payload['previous_model_digest'],'f'*64)
        self.assertEqual(event.payload['manifest_digest'],'a'*64)
        self.assertFalse(self.revision.source_analyses.exists())
        self.assertFalse(self.revision.processing_events.filter(action='technical_approve').exists())

    def test_completed_source_prevents_repin_without_deleting_its_checkpoint(self):
        state=self.prepare()
        analysis=SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:1',payload={'value':'retained'},digest=pipeline.digest({'value':'retained'}))
        with patch('core.survey_model_identity.verified_identity') as verify:
            response=self.post('photo_capture_review_action',self.recovery_payload(state))
        self.assertEqual(response.status_code,409,response.content);verify.assert_not_called()
        self.job.refresh_from_db();self.assertEqual(self.job.model_digest,'f'*64)
        analysis.refresh_from_db();self.assertEqual(analysis.payload,{'value':'retained'})

    def assert_blocked_without_model_request(self):
        state=self.qa_state();self.assertFalse(state['model_recovery']['available'])
        with patch('core.survey_model_identity.verified_identity') as verify:
            response=self.post('photo_capture_review_action',self.recovery_payload(state))
        self.assertEqual(response.status_code,409,response.content);verify.assert_not_called()
        self.job.refresh_from_db();self.assertEqual(self.job.model_digest,'f'*64)
        self.assertFalse(self.revision.processing_events.filter(action='qa_model_recovery').exists())

    def test_saved_result_prevents_repin_even_when_source_checkpoint_count_is_zero(self):
        self.prepare();payload={'checklist_items':[],'findings':[]}
        record=SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        self.assert_blocked_without_model_request()
        record.refresh_from_db();self.assertEqual(record.payload,payload)

    def test_recorded_completion_alone_blocks_recovery_even_without_source_rows(self):
        self.prepare();self.job.completed=1;self.job.save(update_fields=['completed'])
        self.assertFalse(self.revision.source_analyses.exists())
        self.assert_blocked_without_model_request()

    def test_saved_drawing_prevents_repin_and_remains_recoverable(self):
        self.prepare()
        record=SurveyDrawingSet.objects.create(revision=self.revision,edition=1,released=False,
            review_digest='a'*64,geometry={'sheets':[]},manifest={'source_limitations':['Synthetic test drawing']})
        self.assert_blocked_without_model_request()
        record.refresh_from_db();self.assertEqual(record.manifest['source_limitations'],['Synthetic test drawing'])

    def test_approved_sections_and_completed_qa_package_prevent_repin(self):
        self.prepare();self.checklist.refresh_from_db()
        self.checklist.section_approvals={'general':{'by':'Retained reviewer'}}
        self.checklist.save(update_fields=['section_approvals'])
        self.assert_blocked_without_model_request()

    def test_completed_qa_package_is_not_reopened_by_model_recovery(self):
        self.prepare();self.complete_qa_manually()
        self.assert_blocked_without_model_request()

    def test_wrong_role_stale_source_stale_review_and_stale_model_fail_without_metadata_call(self):
        state=self.prepare();base=self.recovery_payload(state)
        with patch('core.survey_model_identity.verified_identity') as verify:
            for actor in [self.engineer,self.lead,self.admin,self.customer]:
                response=self.post('photo_capture_review_action',base,actor=actor)
                self.assertIn(response.status_code,[403,404],response.content)
            self.client.force_login(self.quality)
            for key in ['revision_id','source_digest','expected_review_digest','expected_model_digest']:
                data={**base,key:999999 if key=='revision_id' else '0'*64}
                response=self.post('photo_capture_review_action',data)
                self.assertEqual(response.status_code,409,(key,response.content))
            verify.assert_not_called()
        self.job.refresh_from_db();self.assertEqual(self.job.model_digest,'f'*64)

    def test_unavailable_metadata_and_database_failure_leave_job_untouched(self):
        state=self.prepare();payload=self.recovery_payload(state)
        with patch('core.survey_model_identity.verified_identity',side_effect=ValueError('Unavailable metadata')):
            self.assertEqual(self.post('photo_capture_review_action',payload).status_code,400)
        with patch('core.survey_model_identity.verified_identity',return_value=self.selected),patch(
            'core.survey_model_identity.SurveyProcessingEvent.objects.create',side_effect=DatabaseError('Injected transaction failure')):
            response=self.post('photo_capture_review_action',payload)
            self.assertEqual(response.status_code,409,response.content)
        self.job.refresh_from_db()
        self.assertEqual((self.job.status,self.job.model_digest),('failed','f'*64))
        self.assertFalse(self.revision.processing_events.filter(action='qa_model_recovery').exists())

    def test_metadata_is_read_before_write_lock_then_job_changes_are_rechecked(self):
        state=self.prepare();payload=self.recovery_payload(state)
        outer_savepoints=len(connection.savepoint_ids)
        def race(*args):
            self.assertEqual(len(connection.savepoint_ids),outer_savepoints,
                'Metadata must not hold the QA write transaction')
            self.job.status='analysing_evidence';self.job.save(update_fields=['status'])
            return self.selected
        with patch('core.survey_model_identity.verified_identity',side_effect=race):
            response=self.post('photo_capture_review_action',payload)
        self.assertEqual(response.status_code,409,response.content)
        self.job.refresh_from_db();self.assertEqual(self.job.model_digest,'f'*64)
        self.assertEqual(self.job.status,'analysing_evidence')
        self.assertFalse(self.revision.processing_events.filter(action='qa_model_recovery').exists())

    def test_old_pin_never_silently_rebinds_but_exact_legacy_proof_migrates(self):
        self.prepare()
        self.job.status='queued';self.job.model_digest=self.selected['legacy_fingerprint']
        self.job.save(update_fields=['status','model_digest'])
        stack,_,_=self.processing()
        with patch('core.survey_model_identity.verified_identity',return_value=self.selected):
            self.assertTrue(pipeline.process_next())
        stack.close();self.job.refresh_from_db()
        self.assertEqual(self.job.status,'ready_for_review',self.job.error)
        self.assertEqual(self.job.model_digest,self.selected['fingerprint'])
        self.assertTrue(self.revision.processing_events.filter(action='model_identity_migrated',payload__proof='exact_legacy_metadata_match').exists())

    def test_unknown_legacy_pin_fails_clearly_and_preserves_cached_source(self):
        self.prepare();self.job.status='queued';self.job.save(update_fields=['status'])
        saved={'source_id':'photo:1','findings':[]}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:1',payload=saved,digest=pipeline.digest(saved))
        with patch('core.survey_model_identity.verified_identity',return_value=self.selected):
            self.assertTrue(pipeline.process_next())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status,'failed');self.assertTrue(self.job.error.startswith(identity.MISMATCH))
        self.assertEqual(self.job.model_digest,'f'*64)
        self.assertEqual(self.revision.source_analyses.get().payload,saved)
        self.assertFalse(self.qa_state()['model_recovery']['available'])


from . import test_remote_survey_worker as remote_fixture


@override_settings(**remote_fixture.SETTINGS)
class RemoteManifestCompatibilityTests(remote_fixture.Fixtures,TestCase):
    def proof(self):
        manifest='a'*64;model='qwen3.5:4b'
        return {'version':identity.VERSION,'model':model,'manifest_digest':manifest,
            'fingerprint':pipeline.digest({'version':identity.VERSION,'model':model,
                'manifest_digest':manifest,'pipeline':pipeline.PIPELINE_VERSION}),'legacy_fingerprint':'c'*64}

    def test_verified_client_generates_proof_before_claim_without_receiving_expected_pin(self):
        from .remote_worker_client import RemoteSurveyClient
        from pathlib import Path
        client=RemoteSurveyClient('https://synthetic.example.invalid',self.token,
            Path(self.photo.original.path).parent/'manifest-client')
        with patch('core.photo_service.ollama',side_effect=[
            {'models':[{'name':'qwen3.5:4b','digest':'a'*64}]},
            {'capabilities':['vision'],'modelfile':'FROM synthetic-verified-store'}]),patch.object(
                client,'request',return_value={'job':None}) as outgoing:
            self.assertFalse(client.process_once())
        payload=outgoing.call_args.args[1]
        expected=pipeline.digest({'model':'qwen3.5:4b','details':{
            'capabilities':['vision'],'modelfile':'FROM synthetic-verified-store'},'pipeline':pipeline.PIPELINE_VERSION})
        self.assertEqual(payload['model_identity']['legacy_fingerprint'],expected)
        self.assertEqual(payload['model_digest'],self.proof()['fingerprint'])

    def test_exact_remote_legacy_proof_migrates_and_audits_without_losing_sources(self):
        from . import remote_worker_service as bridge
        from .models import GovernanceAudit
        self.revision.processing_job.model_digest='c'*64
        self.revision.processing_job.save(update_fields=['model_digest'])
        result={'source_id':'retained-synthetic-source','findings':[]}
        saved=SurveySourceAnalysis.objects.create(revision=self.revision,source_id='retained-synthetic-source',payload=result,digest=pipeline.digest(result))
        proof=self.proof()
        job=bridge.claim(self.credential,{**self.identity,'model_digest':proof['fingerprint'],'model_identity':proof})
        self.assertIsNotNone(job)
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.model_digest,proof['fingerprint'])
        self.assertEqual(SurveySourceAnalysis.objects.get(pk=saved.pk).payload,result)
        self.assertTrue(self.revision.processing_events.filter(action='model_identity_migrated',payload__proof='exact_legacy_metadata_match').exists())
        self.assertTrue(GovernanceAudit.objects.filter(action='remote_worker.model_identity_migrated',project=self.project).exists())

    def test_unknown_remote_pin_or_inconsistent_manifest_cannot_rebind(self):
        from . import remote_worker_service as bridge
        job=self.revision.processing_job;job.model_digest='f'*64;job.save(update_fields=['model_digest'])
        proof=self.proof()
        for invalid in [proof,{**proof,'manifest_digest':'e'*64}]:
            with self.assertRaises(ValidationError):bridge.claim(self.credential,{**self.identity,
                'model_digest':proof['fingerprint'],'model_identity':invalid})
        job.refresh_from_db();self.assertEqual(job.model_digest,'f'*64)
        self.assertEqual(job.attempts,0)
        self.assertFalse(self.revision.processing_events.filter(action='model_identity_migrated').exists())


@override_settings(SECRET_KEY='isolated-resumed-progress',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResumedSurveyProgressTests(TestCase):
    setUp=pipeline_fixture.SurveyProcessingTests.setUp
    person=pipeline_fixture.SurveyProcessingTests.person
    add_photo=pipeline_fixture.SurveyProcessingTests.add_photo
    request=pipeline_fixture.SurveyProcessingTests.request
    analysed=pipeline_fixture.SurveyProcessingTests.analysed
    processing=pipeline_fixture.SurveyProcessingTests.processing

    def test_cached_resume_never_regresses_progress_or_repeats_saved_inference(self):
        third=self.add_photo('red')
        revision,_=pipeline.submit(self.request(),self.checklist.pk,True)
        initial_calls=[]
        def interrupted(source,model,**kwargs):
            initial_calls.append(source['source_id'])
            if source['source_id']=='photo:'+str(third.pk):raise ValueError('Synthetic interrupted third source')
            return self.analysed(source,model)
        first,_,_=self.processing(analyse=interrupted)
        self.assertTrue(pipeline.process_next());first.close()
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.completed,2)
        self.assertEqual(revision.processing_job.status,'failed')
        cached={row.source_id:(row.digest,deepcopy(row.payload)) for row in revision.source_analyses.all()}
        self.assertEqual(len(cached),2)
        pipeline.retry(self.request(),self.checklist.pk,revision.pk)
        resumed,native,_=self.processing()
        saved_progress=[];real_progress=pipeline.progress
        def record(job,*args,**kwargs):
            result=real_progress(job,*args,**kwargs)
            if 'completed' in kwargs:saved_progress.append(job.completed)
            return result
        with patch('core.survey_processing.progress',side_effect=record):
            self.assertTrue(pipeline.process_next())
        resumed.close()
        self.assertEqual(saved_progress,sorted(saved_progress))
        self.assertTrue(all(value>=2 for value in saved_progress),saved_progress)
        self.assertEqual(saved_progress[-1],3)
        self.assertEqual(native.call_count,1,'The two completed source analyses must be reused')
        self.assertEqual(native.call_args.args[0]['source_id'],'photo:'+str(third.pk))
        for row in revision.source_analyses.filter(source_id__in=cached):
            self.assertEqual((row.digest,row.payload),cached[row.source_id])
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status,'ready_for_review',revision.processing_job.error)
