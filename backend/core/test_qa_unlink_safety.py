"""Existing matching service contract for explicit unlink and duplicate-safe linking."""
from copy import deepcopy
import hashlib
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from . import qa_matching, test_qa_batch_links as fixtures
from .category_intake import reviewed_payload
from .models import PhotoEvidence
from .survey_processing import review_digest
from .survey_processing_models import SurveyProcessingEvent


@override_settings(SECRET_KEY='isolated-unlink-safety', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAUnlinkSafetyTests(TestCase):
    setUp = fixtures.QABatchLinkTests.setUp
    person = fixtures.QABatchLinkTests.person
    add_photo = fixtures.QABatchLinkTests.add_photo
    post = fixtures.QABatchLinkTests.post
    state = fixtures.QABatchLinkTests.state
    raw = fixtures.QABatchLinkTests.raw
    upload = fixtures.QABatchLinkTests.upload
    submit = fixtures.QABatchLinkTests.submit
    assert_submitted = fixtures.QABatchLinkTests.assert_submitted
    qa_state = fixtures.QABatchLinkTests.qa_state
    qa_action = fixtures.QABatchLinkTests.qa_action
    route = fixtures.QABatchLinkTests.route
    complete_qa_manually = fixtures.QABatchLinkTests.complete_qa_manually
    mutate = fixtures.QABatchLinkTests.mutate
    batch = fixtures.QABatchLinkTests.batch

    def seed_links(self):
        response = self.batch(field_ids=['civil_photo', 'manufacturer'])
        self.assertEqual(response.status_code, 200, response.content)
        return self.qa_state()

    def pairs(self):
        return {(link['photo_id'], link['field_id']) for link in self.qa_state()['links']}

    def source_hash(self, photo):
        with photo.original.storage.open(photo.original.name, 'rb') as stream:
            return hashlib.sha256(stream.read()).hexdigest()

    def test_http_duplicate_pair_is_idempotent_but_other_valid_checkpoint_is_allowed(self):
        self.seed_links()
        before = self.revision.processing_events.count()
        response = self.batch(field_ids=['civil_photo', 'manufacturer'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.revision.processing_events.count(), before)
        self.assertEqual(self.pairs(), {(pid, field) for pid in self.ids[:2] for field in ['civil_photo', 'manufacturer']})
        response = self.batch(field_ids=['electric_photo'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(self.pairs()), 6)

    def test_unit_duplicate_confirmation_creates_no_event_or_duplicate_source(self):
        self.seed_links()
        payload = reviewed_payload(self.revision)
        before = self.revision.processing_events.count()
        qa_matching.action(self.revision, self.checklist, self.quality, {
            'action': 'batch_links', 'operation': 'link', 'photo_ids': self.ids[:2],
            'field_ids': ['civil_photo'], 'template_id': self.template.pk,
            'revision_id': self.revision.pk, 'source_digest': self.revision.digest,
            'expected_review_digest': review_digest(payload), 'reason': 'Synthetic duplicate retry',
        }, payload)
        self.assertEqual(self.revision.processing_events.count(), before)
        links = qa_matching.link_state(self.revision, reviewed_payload(self.revision))
        self.assertEqual(len(links), len({(link['photo_id'], link['field_id']) for link in links}))

    def test_explicit_batch_unlink_preserves_other_links_original_bytes_answers_and_snapshot(self):
        self.seed_links()
        snapshot = deepcopy(self.revision.snapshot)
        hashes = {photo.pk: self.source_hash(photo)
                  for photo in PhotoEvidence.objects.filter(pk__in=self.ids)}
        response = self.batch('unlink', field_ids=['civil_photo'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.pairs(), {(pid, 'manufacturer') for pid in self.ids[:2]})
        self.assertEqual(response.json()['counts']['assigned'], 2)
        self.assertEqual(response.json()['counts']['unassigned'], 1)
        for photo in PhotoEvidence.objects.filter(pk__in=self.ids):
            self.assertEqual(self.source_hash(photo), hashes[photo.pk])
        self.assertEqual(PhotoEvidence.objects.filter(pk__in=self.ids).count(), 3)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.snapshot, snapshot)
        self.assertFalse(any(item['accepted'] for item in self.qa_state()['items']))

    def test_repeat_unlink_and_mixed_missing_pairs_never_remove_unrelated_links(self):
        self.seed_links()
        self.assertEqual(self.batch('unlink', field_ids=['civil_photo'], photo_ids=self.ids[:1]).status_code, 200)
        before = self.pairs()
        count = self.revision.processing_events.count()
        # Includes one absent pair and one present pair: reject the entire request.
        self.assertEqual(self.batch('unlink', field_ids=['civil_photo']).status_code, 409)
        self.assertEqual(self.batch('unlink', field_ids=['civil_photo'], photo_ids=self.ids[:1]).status_code, 409)
        self.assertEqual(self.pairs(), before)
        self.assertEqual(self.revision.processing_events.count(), count)

    def test_unlink_bulk_save_failure_rolls_back_and_keeps_existing_links(self):
        self.seed_links()
        before = self.pairs()
        count = self.revision.processing_events.count()
        with patch.object(SurveyProcessingEvent.objects, 'bulk_create', side_effect=DatabaseError('Synthetic unlink failure')):
            with self.assertRaises(DatabaseError):
                self.batch('unlink', field_ids=['civil_photo'])
        self.assertEqual(self.pairs(), before)
        self.assertEqual(self.revision.processing_events.count(), count)

    def test_unlink_respects_approved_section_lock(self):
        self.seed_links()
        before = self.pairs()
        self.checklist.section_approvals = {'civil_test': {'by': self.lead.pk}}
        self.checklist.save(update_fields=['section_approvals'])
        count = self.revision.processing_events.count()
        self.assertEqual(self.batch('unlink', field_ids=['civil_photo']).status_code, 409)
        self.assertEqual(self.pairs(), before)
        self.assertEqual(self.revision.processing_events.count(), count)
