"""Explicit recovery for old revisions submitted before automatic retention."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from . import test_qa_resubmission_links as fixtures
from .models import PhotoEvidence,ChecklistTemplate
from copy import deepcopy


@override_settings(SECRET_KEY='isolated-qa-link-recovery',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QARestorePreviousLinksTests(TestCase):
    setUp=fixtures.QAResubmissionLinkTests.setUp
    person=fixtures.QAResubmissionLinkTests.person
    add_photo=fixtures.QAResubmissionLinkTests.add_photo
    post=fixtures.QAResubmissionLinkTests.post
    state=fixtures.QAResubmissionLinkTests.state
    raw=fixtures.QAResubmissionLinkTests.raw
    upload=fixtures.QAResubmissionLinkTests.upload
    submit=fixtures.QAResubmissionLinkTests.submit
    assert_submitted=fixtures.QAResubmissionLinkTests.assert_submitted
    qa_state=fixtures.QAResubmissionLinkTests.qa_state
    qa_action=fixtures.QAResubmissionLinkTests.qa_action
    route=fixtures.QAResubmissionLinkTests.route
    batch=fixtures.QAResubmissionLinkTests.batch
    mutate=fixtures.QAResubmissionLinkTests.mutate

    def legacy_resubmit(self):
        self.assertEqual(self.route(self.quality,'reject','Legacy resubmission missing matching carry').status_code,302)
        with patch('core.qa_matching.retain_submission_links'):
            self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        self.assertEqual(self.qa_state()['links'],[])

    def restore(self,**updates):
        state=self.qa_state()
        return self.post('photo_capture_review_action',{'action':'restore_previous_links',
            'revision_id':self.revision.pk,'source_digest':self.revision.digest,
            'expected_review_digest':state['review_digest'],'template_id':self.checklist.checklist_template_id,
            'response_mode':'link_patch',**updates})

    def test_recovery_restores_legacy_empty_resubmission_and_is_idempotent(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        old=self.revision
        self.legacy_resubmit()
        recovered=self.restore()
        self.assertEqual(recovered.status_code,200,recovered.content)
        self.assertEqual(recovered.json()['restored_count'],4)
        self.assertEqual(len(recovered.json()['links_patch']['links']),4)
        self.assertTrue(all(link['retained_from_revision']['id']==old.pk for link in recovered.json()['links_patch']['links']))
        self.assertFalse(any(item['accepted'] for item in self.qa_state()['items']))
        count=self.revision.processing_events.count()
        again=self.restore()
        self.assertEqual(again.status_code,200,again.content)
        self.assertEqual(again.json()['restored_count'],0)
        self.assertIn('No eligible',again.json()['message'])
        self.assertEqual(self.revision.processing_events.count(),count)

    def test_bounded_scan_bridges_empty_legacy_revision_without_inventing_decisions(self):
        self.assertEqual(self.batch().status_code,200)
        self.legacy_resubmit();self.legacy_resubmit()
        restored=self.restore()
        self.assertEqual(restored.status_code,200,restored.content)
        self.assertEqual(restored.json()['restored_count'],2)

    def test_current_unlink_reassign_and_accepted_answer_are_preserved(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        self.legacy_resubmit()
        self.assertEqual(self.mutate('confirm_link',field_id='civil_photo',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.mutate('reassign_link',from_field_id='civil_photo',to_field_id='electric_photo',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.qa_action('answer',field_id='manufacturer',value='Current human correction',
            photo_ids=[],reason='Checked current source').status_code,200)
        result=self.restore()
        self.assertEqual(result.status_code,200,result.content)
        state=self.qa_state()
        self.assertEqual({(link['photo_id'],link['field_id']) for link in state['links']},
            {(self.ids[0],'electric_photo'),(self.ids[1],'civil_photo')})
        item=next(item for item in state['items'] if item['id']=='manufacturer')
        self.assertTrue(item['accepted']);self.assertEqual(item['value'],'Current human correction')

    def test_intervening_explicit_unlink_blocks_older_link(self):
        self.assertEqual(self.batch().status_code,200)
        self.legacy_resubmit()
        self.assertEqual(self.mutate('confirm_link',field_id='civil_photo',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.mutate('unlink',field_id='civil_photo',photo_id=self.ids[0]).status_code,200)
        self.legacy_resubmit()
        result=self.restore()
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['restored_count'],1)
        self.assertEqual([(link['photo_id'],link['field_id']) for link in self.qa_state()['links']],[(self.ids[1],'civil_photo')])

    def test_no_prior_links_returns_honest_noop_and_stale_template_is_rejected(self):
        self.legacy_resubmit()
        result=self.restore()
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['restored_count'],0)
        self.assertEqual(result.json()['links_patch']['links'],[])
        self.assertEqual(self.restore(template_id=self.template.pk+999).status_code,409)
        self.assertEqual(self.restore(expected_review_digest='stale').status_code,409)

    def test_locked_field_recovery_is_atomic(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','electric_photo']).status_code,200)
        self.legacy_resubmit()
        self.checklist.refresh_from_db()
        self.checklist.section_approvals={'electric_test':{'by':self.lead.pk}}
        self.checklist.save(update_fields=['section_approvals'])
        before=self.revision.processing_events.count()
        self.assertEqual(self.restore().status_code,409)
        self.assertEqual(self.revision.processing_events.count(),before)

    def test_excluded_source_and_changed_hash_are_not_recovered(self):
        self.assertEqual(self.batch(field_ids=['civil_photo','manufacturer']).status_code,200)
        self.assertEqual(self.route(self.quality,'reject','Replace old source').status_code,302)
        state=self.state(self.engineer)
        self.assertEqual(self.post('photo_capture_remove',{'photo_id':self.ids[1],'expected_digest':state['digest']}).status_code,200)
        PhotoEvidence.objects.filter(pk=self.ids[0]).update(sha256='9'*64)
        with patch('core.qa_matching.retain_submission_links'):
            self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        result=self.restore()
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['restored_count'],0)

    def test_changed_approved_template_stops_recovery_lineage(self):
        self.assertEqual(self.batch().status_code,200)
        self.assertEqual(self.route(self.quality,'reject','Use another approved template').status_code,302)
        self.checklist.refresh_from_db()
        self.checklist.checklist_template=ChecklistTemplate.objects.create(name='Different approved source',
            definition=deepcopy(self.checklist.schema_snapshot),published=True)
        self.checklist.save(update_fields=['checklist_template'])
        with patch('core.qa_matching.retain_submission_links'):
            self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        result=self.restore()
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['restored_count'],0)

    def test_changed_schema_stops_recovery_lineage(self):
        self.assertEqual(self.batch().status_code,200)
        self.assertEqual(self.route(self.quality,'reject','Use revised approved schema').status_code,302)
        self.checklist.refresh_from_db()
        schema=deepcopy(self.checklist.schema_snapshot)
        schema['sections'][0]['fields'][2]['label']+=' revised'
        self.checklist.schema_snapshot=schema
        ChecklistTemplate.objects.filter(pk=self.template.pk).update(definition=schema)
        self.checklist.save(update_fields=['schema_snapshot'])
        with patch('core.qa_matching.retain_submission_links'):
            self.assertEqual(self.submit(actor=self.engineer)[0].status_code,201)
        self.revision=self.checklist.processing_revisions.latest('number')
        self.assertEqual(self.restore().json()['restored_count'],0)
