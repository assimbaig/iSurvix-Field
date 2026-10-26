"""Matching associations survive valid source resubmission; approvals do not."""
from copy import deepcopy
from django.test import TestCase, override_settings
from . import test_qa_batch_links as fixtures, survey_processing as pipeline
from .models import PhotoEvidence, ChecklistTemplate
from .survey_processing_models import SurveyProcessingResult
from . import test_survey_processing as worker_fixtures


@override_settings(SECRET_KEY='isolated-qa-resubmission-links',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAResubmissionLinkTests(TestCase):
    setUp=fixtures.QABatchLinkTests.setUp
    person=fixtures.QABatchLinkTests.person
    add_photo=fixtures.QABatchLinkTests.add_photo
    post=fixtures.QABatchLinkTests.post
    state=fixtures.QABatchLinkTests.state
    raw=fixtures.QABatchLinkTests.raw
    upload=fixtures.QABatchLinkTests.upload
    submit=fixtures.QABatchLinkTests.submit
    assert_submitted=fixtures.QABatchLinkTests.assert_submitted
    qa_state=fixtures.QABatchLinkTests.qa_state
    qa_action=fixtures.QABatchLinkTests.qa_action
    route=fixtures.QABatchLinkTests.route
    batch=fixtures.QABatchLinkTests.batch
    mutate=fixtures.QABatchLinkTests.mutate
    analysed=worker_fixtures.SurveyProcessingTests.analysed
    processing=worker_fixtures.SurveyProcessingTests.processing

    def reject(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        self.assertEqual(self.route(self.quality,'reject','Additional source details needed').status_code,302)
        self.client.force_login(self.engineer)

    def resubmit(self):
        old=self.revision
        self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        self.assertNotEqual(old.pk,self.revision.pk)
        return self.qa_state()

    def test_full_rejection_resubmit_retains_links_while_queued_without_answers_or_approval(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        accepted=self.qa_action('answer',field_id='manufacturer',value='Human prior answer',
            photo_ids=self.ids[:2],reason='Read original labels')
        self.assertEqual(accepted.status_code,200)
        before=self.qa_state();old=self.revision
        self.assertEqual(self.route(self.quality,'reject','Add source details').status_code,302)
        after=self.resubmit()
        self.assertEqual(after['ai']['status'],'queued')
        self.assertEqual({(link['photo_id'],link['field_id']) for link in before['links']},
            {(link['photo_id'],link['field_id']) for link in after['links']})
        self.assertTrue(all(link['state']=='qa_confirmed' for link in after['links']))
        for link in after['links']:
            self.assertEqual(link['retained_from_revision'],{'id':old.pk,'number':old.number})
            self.assertEqual(link['origin_matching_actor'],self.quality.pk)
        item=next(item for item in after['items'] if item['id']=='manufacturer')
        self.assertFalse(item['accepted']);self.assertIsNone(item['value'])
        self.assertFalse(after['completed'])
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.quality_approval,{})
        self.assertEqual(self.checklist.client_approval,{})
        self.assertEqual(self.checklist.section_approvals,{})
        self.assertFalse(self.revision.processing_events.filter(action__in=['qa_complete','technical_approve']).exists())
        events=self.revision.processing_events.filter(action='qa_link_retained')
        self.assertTrue(events.exists())
        self.assertTrue(all(event.actor_id==self.engineer.pk for event in events))

    def test_removed_photo_and_explicitly_removed_link_are_not_retained(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        self.assertEqual(self.mutate('unlink',field_id='manufacturer',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.route(self.quality,'reject','Replace a source').status_code,302)
        state=self.state(self.engineer)
        self.assertEqual(self.post('photo_capture_remove',{'photo_id':self.ids[1],'expected_digest':state['digest']}).status_code,200)
        after=self.resubmit()
        self.assertEqual([(link['photo_id'],link['field_id']) for link in after['links']],[(self.ids[0],'civil_photo')])

    def test_changed_hash_does_not_retain_old_associations(self):
        self.reject()
        for index,pid in enumerate(self.ids[:2]):
            PhotoEvidence.objects.filter(pk=pid).update(sha256=str(index+7)*64)
        self.assertEqual(self.resubmit()['links'],[])

    def test_changed_schema_does_not_retain_old_associations(self):
        self.reject();self.checklist.refresh_from_db()
        schema=deepcopy(self.checklist.schema_snapshot)
        schema['sections'][0]['fields'][2]['label']+=' changed'
        self.checklist.schema_snapshot=schema
        ChecklistTemplate.objects.filter(pk=self.template.pk).update(definition=schema)
        self.checklist.save(update_fields=['schema_snapshot'])
        self.assertEqual(self.resubmit()['links'],[])

    def test_changed_template_does_not_retain_old_associations(self):
        self.reject();self.checklist.refresh_from_db()
        self.checklist.checklist_template=ChecklistTemplate.objects.create(name='New source lineage',
            definition=deepcopy(self.checklist.schema_snapshot),published=True)
        self.checklist.save(update_fields=['checklist_template'])
        self.assertEqual(self.resubmit()['links'],[])

    def test_late_ai_does_not_replace_retained_matching_or_restore_removed_link(self):
        self.reject();after=self.resubmit()
        self.assertEqual(len(after['links']),4)
        findings=[{'source_id':'photo:'+str(self.ids[0]),'field_hint':'civil_photo','value':'Late observation',
            'confidence':'high','evidence_quote':'Late model text','basis':'recorded'}]
        package=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=package,digest=pipeline.digest(package))
        self.revision.processing_job.status='ready_for_review';self.revision.processing_job.save(update_fields=['status'])
        late=self.qa_state()
        self.assertEqual(len(late['links']),4)
        self.assertTrue(all(link['state']=='qa_confirmed' for link in late['links']))
        self.assertEqual(self.mutate('unlink',field_id='civil_photo',photo_id=self.ids[0]).status_code,200)
        again=self.qa_state()
        self.assertNotIn((self.ids[0],'civil_photo'),[(link['photo_id'],link['field_id']) for link in again['links']])

    def test_worker_reuses_actual_input_cache_without_losing_retained_matching(self):
        first=self.revision
        stack,model,_=self.processing()
        self.assertTrue(pipeline.process_next())
        self.assertEqual(model.call_count,3)
        stack.close()
        self.reject()
        pending=self.resubmit()
        retained={(link['photo_id'],link['field_id']) for link in pending['links'] if link['state']=='qa_confirmed'}
        self.assertEqual(len(retained),4)
        stack,model,_=self.processing()
        self.assertTrue(pipeline.process_next())
        self.revision.processing_job.refresh_from_db()
        self.assertEqual(self.revision.processing_job.status,'ready_for_review',self.revision.processing_job.error)
        self.assertEqual(model.call_count,0,'Same actual image inputs must reuse retained raw analysis')
        for row in self.revision.source_analyses.exclude(source_id__startswith='mapping:'):
            self.assertTrue(row.payload['performance']['cache_hit'])
            self.assertEqual(row.payload['acceleration']['reused_from']['revision_id'],first.pk)
        final=self.qa_state()
        self.assertEqual({(link['photo_id'],link['field_id']) for link in final['links'] if link['state']=='qa_confirmed'},retained)
        self.assertFalse(any(item['accepted'] for item in final['items']))
        stack.close()
