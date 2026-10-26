"""Atomic batch assignment and compact HTTP responses, isolated synthetic data."""
from copy import deepcopy
import json
import time
from unittest.mock import patch
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from . import test_qa_matching_backend as fixtures, qa_matching
from .survey_processing_models import SurveyProcessingEvent


@override_settings(SECRET_KEY='isolated-qa-batch-links',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QABatchLinkTests(TestCase):
    setUp=fixtures.QAMatchingBackendTests.setUp
    person=fixtures.QAMatchingBackendTests.person
    add_photo=fixtures.QAMatchingBackendTests.add_photo
    post=fixtures.QAMatchingBackendTests.post
    state=fixtures.QAMatchingBackendTests.state
    raw=fixtures.QAMatchingBackendTests.raw
    upload=fixtures.QAMatchingBackendTests.upload
    submit=fixtures.QAMatchingBackendTests.submit
    assert_submitted=fixtures.QAMatchingBackendTests.assert_submitted
    qa_state=fixtures.QAMatchingBackendTests.qa_state
    qa_action=fixtures.QAMatchingBackendTests.qa_action
    route=fixtures.QAMatchingBackendTests.route
    complete_qa_manually=fixtures.QAMatchingBackendTests.complete_qa_manually
    mutate=fixtures.QAMatchingBackendTests.mutate

    def batch(self,operation='link',**updates):
        state=self.qa_state()
        data={'action':'batch_links','operation':operation,'photo_ids':self.ids[:2],
            'field_ids':['civil_photo'],'template_id':self.template.pk,
            'revision_id':state['revision_id'],'source_digest':state['source_digest'],
            'expected_review_digest':state['review_digest'],'response_mode':'link_patch',
            'reason':'Checked original source and selected this checkpoint',**updates}
        return self.post('photo_capture_review_action',data)

    def test_batch_links_and_move_preserve_unrelated_links_and_answers(self):
        frozen=deepcopy(self.revision.snapshot)
        result=self.batch(field_ids=['civil_photo','manufacturer'])
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(len(result.json()['links_patch']['links']),4)
        moved=self.batch('move',from_field_id='civil_photo',field_ids=['electric_photo'])
        self.assertEqual(moved.status_code,200,moved.content)
        state=self.qa_state()
        self.assertEqual({(x['photo_id'],x['field_id']) for x in state['links']},
            {(pid,fid) for pid in self.ids[:2] for fid in ['manufacturer','electric_photo']})
        self.assertFalse(any(item['accepted'] for item in state['items']))
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,frozen)
        self.assertEqual(moved.json()['review_digest'],state['review_digest'])
        self.assertEqual(moved.json()['counts'],state['counts'])

    def test_compact_avoids_full_projection_and_legacy_shape_remains(self):
        with patch('core.category_intake.review_state',side_effect=AssertionError('full projection forbidden')):
            result=self.batch_without_state()
        self.assertEqual(result.status_code,200,result.content)
        result=result.json()
        self.assertNotIn('photos',result);self.assertNotIn('observations',result)
        self.assertNotIn('matching_history',result)
        self.assertEqual(result['response_mode'],'link_patch')
        self.assertIn('can_complete',result);self.assertIn('progress_token',result)
        legacy=self.mutate('confirm_link',photo_id=self.ids[2],field_id='civil_photo')
        self.assertEqual(legacy.status_code,200,legacy.content)
        self.assertIn('photos',legacy.json());self.assertNotIn('response_mode',legacy.json())

    def batch_without_state(self):
        from .category_intake import reviewed_payload
        from .survey_processing import review_digest
        self.client.force_login(self.quality)
        return self.post('photo_capture_review_action',{'action':'batch_links','operation':'link',
            'photo_ids':self.ids[:2],'field_ids':['civil_photo'],'template_id':self.template.pk,
            'revision_id':self.revision.pk,'source_digest':self.revision.digest,
            'expected_review_digest':review_digest(reviewed_payload(self.revision)),
            'response_mode':'link_patch','reason':'Independently checked source'})

    def test_invalid_member_locked_target_and_stale_digest_are_atomic(self):
        before=self.revision.processing_events.count()
        for invalid in [{'photo_ids':[self.ids[0],self.photo.pk]},
            {'photo_ids':[True]}, {'photo_ids':[self.ids[0],self.ids[0]]},
            {'field_ids':['civil_photo','unknown']}, {'template_id':self.template.pk+999},
            {'expected_review_digest':'old'}, {'field_ids':[]},
            {'operation':'move','from_field_id':'civil_photo'}]:
            response=self.batch(**invalid)
            self.assertEqual(response.status_code,409,(invalid,response.content))
            self.assertEqual(self.revision.processing_events.count(),before)
        self.checklist.section_approvals={'electric_test':{'by':self.lead.pk}}
        self.checklist.save(update_fields=['section_approvals'])
        response=self.batch(field_ids=['civil_photo','electric_photo'])
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(self.revision.processing_events.count(),before)

    def test_failed_bulk_persistence_rolls_back_every_link(self):
        before=self.revision.processing_events.count()
        from django.db import DatabaseError
        with patch.object(SurveyProcessingEvent.objects,'bulk_create',side_effect=DatabaseError('fixture write failure')):
            with self.assertRaises(DatabaseError):self.batch()
        self.assertEqual(self.revision.processing_events.count(),before)
        self.assertEqual(self.qa_state()['links'],[])

    def test_replay_unit_batch_matches_single_action_and_reason_is_audited(self):
        from .category_intake import reviewed_payload
        from .survey_processing import review_digest
        payload=reviewed_payload(self.revision)
        qa_matching.action(self.revision,self.checklist,self.quality,{'action':'batch_links','operation':'link',
            'photo_ids':self.ids[:2],'field_ids':['civil_photo'],'template_id':self.template.pk,
            'revision_id':self.revision.pk,'source_digest':self.revision.digest,
            'expected_review_digest':review_digest(payload),'reason':'Unit source review'},payload)
        replayed=reviewed_payload(self.revision)
        self.assertEqual(qa_matching.link_state(self.revision,payload),qa_matching.link_state(self.revision,replayed))
        events=self.revision.processing_events.filter(action='qa_link')
        self.assertEqual(events.count(),2)
        self.assertTrue(all(e.reason=='Unit source review' and e.actor_id==self.quality.pk for e in events))

    def test_performance_receipt(self):
        # Repeated long observations model a moderately dense submitted package.
        from . import survey_processing as pipeline
        from .survey_processing_models import SurveyProcessingResult,SurveySourceAnalysis
        findings=[{'source_id':'photo:'+str(self.ids[0]),'field_hint':'manufacturer','value':'SyntheticCo',
            'confidence':'high','evidence_quote':'Recorded label '+('label detail '*30),'component':'cabinet',
            'finding_key':'photo:'+str(self.ids[0])+':finding:'+str(i)} for i in range(250)]
        package=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=package,digest=pipeline.digest(package))
        observation={'findings':findings,'reference':'original'}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:'+str(self.ids[0]),
            payload=observation,digest=pipeline.digest(observation))
        initial=self.qa_state()
        base={'revision_id':self.revision.pk,'source_digest':self.revision.digest,
            'expected_review_digest':initial['review_digest'],'template_id':self.template.pk,
            'action':'confirm_link','photo_id':self.ids[0],'field_id':'civil_photo','reason':'Performance source review'}
        start=time.perf_counter()
        with CaptureQueriesContext(connection) as full_queries:full=self.post('photo_capture_review_action',base)
        full_ms=(time.perf_counter()-start)*1000
        self.assertEqual(full.status_code,200,full.content)
        base.update(expected_review_digest=full.json()['review_digest'],photo_id=self.ids[1],response_mode='link_patch')
        start=time.perf_counter()
        with CaptureQueriesContext(connection) as compact_queries:compact=self.post('photo_capture_review_action',base)
        compact_ms=(time.perf_counter()-start)*1000
        self.assertEqual(compact.status_code,200,compact.content)
        self.assertLess(len(compact.content),len(full.content)//5)
        self.assertLess(len(compact_queries),len(full_queries))
        print('QA_BATCH_PERFORMANCE '+json.dumps({'observations':250,'photos':3,
            'full_bytes':len(full.content),'compact_bytes':len(compact.content),
            'full_queries':len(full_queries),'compact_queries':len(compact_queries),
            'full_ms':round(full_ms,2),'compact_ms':round(compact_ms,2)}))

    def test_large_collection_performance_receipt(self):
        from . import survey_processing as pipeline
        from .survey_processing_models import SurveyProcessingResult,SurveySourceAnalysis
        self.assertEqual(self.route(self.quality,'reject','Expand synthetic collection for response benchmark').status_code,302)
        for index in range(97):self.add_photo('#'+format(index+100,'06x'))
        self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        findings=[];records=[]
        for photo in self.revision.snapshot['photos']:
            source='photo:'+str(photo['id'])
            observed=[{'source_id':source,'field_hint':'manufacturer','value':'SyntheticCo',
                'confidence':'high','evidence_quote':'Synthetic dense source transcription '+('label detail '*60),
                'component':'cabinet','finding_key':source+':finding:'+str(i)} for i in range(50)]
            findings.extend(observed)
            payload={'findings':observed,'reference':'original'}
            records.append(SurveySourceAnalysis(revision=self.revision,source_id=source,
                payload=payload,digest=pipeline.digest(payload)))
        SurveySourceAnalysis.objects.bulk_create(records)
        package=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=package,digest=pipeline.digest(package))
        initial=self.qa_state()
        data={'action':'confirm_link','photo_id':self.ids[0],'field_id':'civil_photo',
            'revision_id':self.revision.pk,'source_digest':self.revision.digest,'template_id':self.template.pk,
            'expected_review_digest':initial['review_digest'],'reason':'Synthetic large-collection performance measurement'}
        started=time.perf_counter()
        with CaptureQueriesContext(connection) as full_queries:full=self.post('photo_capture_review_action',data)
        full_ms=(time.perf_counter()-started)*1000
        self.assertEqual(full.status_code,200,full.content[:500])
        data.update(photo_id=self.ids[1],expected_review_digest=full.json()['review_digest'],response_mode='link_patch')
        started=time.perf_counter()
        with CaptureQueriesContext(connection) as compact_queries:compact=self.post('photo_capture_review_action',data)
        compact_ms=(time.perf_counter()-started)*1000
        self.assertEqual(compact.status_code,200,compact.content[:500])
        self.assertLess(len(compact.content),len(full.content)//100)
        self.assertLess(len(compact_queries),len(full_queries))
        print('QA_LARGE_COLLECTION_PERFORMANCE '+json.dumps({'photos':100,'observations_per_photo':50,
            'full_bytes':len(full.content),'compact_bytes':len(compact.content),
            'full_queries':len(full_queries),'compact_queries':len(compact_queries),
            'full_ms':round(full_ms,2),'compact_ms':round(compact_ms,2)}))
