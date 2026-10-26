"""Approved M1/C1 repairs: isolated source-backed matching and immutable history."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from . import qa_matching, survey_checklist_mapping as mapping, survey_processing as pipeline
from . import test_survey_processing as processing_fixtures
from . import test_qa_matching_backend as matching_fixtures
from . import test_remote_survey_worker as remote_fixtures
from . import remote_worker_service as bridge
from .survey_processing_models import SurveySourceAnalysis


class SourceSupportTests(SimpleTestCase):
    def sources(self, **finding):
        source = {'source_id': 'photo:17', 'reference': 'synthetic.png'}
        return qa_matching.valid_ai_sources(
            {'id': 'inspection', 'sources': [source]},
            [{'source_id': 'photo:17', 'field_hint': 'inspection', 'confidence': 'high', **finding}])

    def test_generated_mapping_explanation_is_not_original_source_support(self):
        self.assertEqual(self.sources(value=None, component='', notes='', evidence_quote='',
            mapping_reason='The image analysis proposed this supported checklist location.'), [])

    def test_actual_zero_false_and_unanswered_observations_remain_supported(self):
        for finding in [{'value': 0}, {'value': False}, {'component': 'Visible footing'},
                        {'notes': 'The source shows a cabinet door.'}, {'evidence_quote': '0 A'}]:
            with self.subTest(finding=finding):
                self.assertEqual(len(self.sources(**finding)), 1)

    def test_whitespace_value_or_explanation_does_not_supply_evidence(self):
        self.assertEqual(self.sources(value=' \t ', component=' ', notes='', evidence_quote='',
            mapping_reason='Generated explanation'), [])


@override_settings(SECRET_KEY='isolated-matching-readiness-repairs', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SourceSupportIntegrationTests(TestCase):
    setUp = processing_fixtures.SurveyProcessingTests.setUp
    person = processing_fixtures.SurveyProcessingTests.person
    request = processing_fixtures.SurveyProcessingTests.request
    add_photo = processing_fixtures.SurveyProcessingTests.add_photo
    processing = processing_fixtures.SurveyProcessingTests.processing
    analysed = processing_fixtures.SurveyProcessingTests.analysed

    def process(self, finding):
        originals = {photo.pk: Path(photo.original.path).read_bytes()
            for photo in self.checklist.photo_evidence.all()}
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        snapshot = deepcopy(revision.snapshot)

        def analysis(source, model, **kwargs):
            return {'source_id': source['source_id'], 'reference': source['reference'],
                'model': model, 'findings': [{'category': 'equipment', 'confidence': 'high',
                    'value': None, 'component': '', 'notes': '', 'evidence_quote': '',
                    'field_hint': 'manufacturer', **finding}]}

        self.processing(analyse=analysis)
        self.assertTrue(pipeline.process_next())
        revision.processing_job.refresh_from_db()
        self.assertEqual(revision.processing_job.status, 'ready_for_review', revision.processing_job.error)
        payload = pipeline.reviewed_payload(revision)
        result = qa_matching.state(revision, payload, self.quality)
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot, snapshot)
        self.assertEqual(originals, {photo.pk: Path(photo.original.path).read_bytes()
            for photo in self.checklist.photo_evidence.all()})
        self.assertFalse(any(item['accepted'] for item in payload['checklist_items']))
        return result

    def test_empty_high_confidence_worker_output_cannot_create_suggested_links(self):
        result = self.process({})
        self.assertEqual(result['links'], [])
        self.assertEqual(result['counts']['assigned'], 0)
        self.assertEqual(result['counts']['unassigned'], 2)
        self.assertTrue(all(item['status'] == 'unmatched' for item in result['photo_matches'].values()))

    def test_unanswered_real_inspection_source_still_proposes_location_without_acceptance(self):
        result = self.process({'field_hint': 'cabinet_condition', 'component': 'Cabinet door',
            'notes': 'A cabinet door is visible; the inspection decision is not established.'})
        self.assertEqual(result['counts']['suggested'], 2)
        self.assertTrue(all(link['field_id'] == 'cabinet_condition' and link['state'] == 'ai_suggested'
            for link in result['links']))

    def test_actual_worker_persists_a_context_receipt_before_whole_revision_completion(self):
        revision, _ = pipeline.submit(self.request(), self.checklist.pk, True)

        def analysis(source, model, **kwargs):
            return {'source_id': source['source_id'], 'reference': source['reference'], 'model': model,
                'findings': [{'component': 'Cabinet manufacturer', 'value': 'SyntheticCo',
                    'confidence': 'high', 'field_hint': '', 'basis': 'recorded'}]}

        def decisions(path, payload, **kwargs):
            keys = payload['format']['properties']['decisions']['properties']
            return {'message': {'content': json.dumps({'decisions': {key: {
                'field_id': 'manufacturer', 'reason': 'The recorded manufacturer label.'} for key in keys}})}}

        self.processing(analyse=analysis)
        with patch.object(mapping.local_ai, 'ollama', side_effect=decisions), \
                patch.object(pipeline, 'prepare_checklist', side_effect=ValueError('Isolated stop after saved mapping')):
            self.assertTrue(pipeline.process_next())
        job = revision.processing_job
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        analyses = [entry.payload for entry in revision.source_analyses.exclude(source_id__startswith='mapping:')]
        context = mapping.partial_mapping_context(analyses, revision.snapshot['schema'], job.model, job.model_digest)
        saved = revision.source_analyses.get(source_id__startswith='mapping:')
        self.assertTrue(mapping.verified_partial_mapping(saved.source_id, saved.payload, context))
        before = list(revision.source_analyses.values_list('source_id', 'payload', 'digest'))
        job.status = 'preparing_checklist'; job.save(update_fields=['status'])
        payload = pipeline.prepare_checklist(revision.snapshot, {'findings': [], 'missing': [], 'conflicts': []})
        result = qa_matching.state(revision, payload, self.quality)
        self.assertTrue(all(photo['status'] == 'proposed' for photo in result['photo_matches'].values()))
        self.assertFalse(any(item['accepted'] for item in payload['checklist_items']))
        self.assertEqual(list(revision.source_analyses.values_list('source_id', 'payload', 'digest')), before)


@override_settings(SECRET_KEY='isolated-partial-mapping-context-repairs', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PartialMappingContextTests(TestCase):
    setUp = matching_fixtures.QAMatchingBackendTests.setUp
    person = matching_fixtures.QAMatchingBackendTests.person
    add_photo = matching_fixtures.QAMatchingBackendTests.add_photo
    post = matching_fixtures.QAMatchingBackendTests.post
    state = matching_fixtures.QAMatchingBackendTests.state
    raw = matching_fixtures.QAMatchingBackendTests.raw
    upload = matching_fixtures.QAMatchingBackendTests.upload
    submit = matching_fixtures.QAMatchingBackendTests.submit
    assert_submitted = matching_fixtures.QAMatchingBackendTests.assert_submitted
    qa_state = matching_fixtures.QAMatchingBackendTests.qa_state

    def seed_partial(self, obsolete=False, wrong_binding=False, receipt=False, context_overrides=None):
        source_id = 'photo:' + str(self.ids[0])
        raw = {'source_id': source_id, 'reference': 'synthetic-active-label.png', 'findings': [
            {'component': 'cabinet manufacturer', 'value': 'SyntheticCo', 'confidence': 'high'}]}
        batch = list(mapping.mapping_batches([raw], self.revision.snapshot['schema']))[0]
        job = self.revision.processing_job
        job.status = 'preparing_checklist'; job.model_digest = 'a' * 64
        job.save(update_fields=['status', 'model_digest'])
        mapped = mapping._with_candidates(batch, {'bindings': [
            {'finding_key': batch['findings'][0]['finding_key'], 'field_id': 'manufacturer',
             'reason': 'STALE_CONTEXT must not be exposed as current advice.'}], 'unassigned': [],
             'identity': 'obsolete-model' if wrong_binding else mapping.binding_identity(batch, job.model),
             'batch_identity': 'obsolete-batch' if obsolete else batch['identity']})
        if receipt:
            context = mapping.partial_mapping_context([raw], self.revision.snapshot['schema'],
                job.model, job.model_digest)
            context.update(context_overrides or {})
            mapped = mapping.with_partial_mapping_context(batch, mapped, context)
        for source, payload in [(source_id, raw), ('mapping:0001' if obsolete else batch['key'], mapped)]:
            SurveySourceAnalysis.objects.create(revision=self.revision, source_id=source,
                payload=payload, digest=pipeline.digest(payload))
        return raw, batch, mapped

    def assert_advice_withheld(self):
        before = list(self.revision.source_analyses.values_list('source_id', 'payload', 'digest'))
        result = self.qa_state()
        first = next(photo for photo in result['photos'] if photo['id'] == self.ids[0])
        self.assertEqual(first['photo_match']['status'], 'pending')
        self.assertEqual(first['photo_match']['candidates'], [])
        self.assertNotIn('STALE_CONTEXT', str(result))
        self.assertEqual(result['links'], [])
        self.assertEqual(list(self.revision.source_analyses.values_list('source_id', 'payload', 'digest')), before)

    def test_obsolete_retained_batch_and_model_context_do_not_appear_as_current_advice(self):
        self.seed_partial(obsolete=True, wrong_binding=True)
        self.assert_advice_withheld()

    def test_wrong_model_binding_identity_does_not_appear_as_current_advice(self):
        self.seed_partial(wrong_binding=True)
        self.assert_advice_withheld()

    def test_receiptless_partial_mapping_is_retained_without_unverified_advice(self):
        self.seed_partial()
        self.assert_advice_withheld()

    def test_stale_source_receipt_is_retained_without_unverified_advice(self):
        self.seed_partial(receipt=True, context_overrides={'sources_digest': 'b' * 64})
        self.assert_advice_withheld()

    def test_stale_schema_receipt_is_retained_without_unverified_advice(self):
        self.seed_partial(receipt=True, context_overrides={'schema_digest': 'b' * 64})
        self.assert_advice_withheld()

    def test_stale_code_receipt_is_retained_without_unverified_advice(self):
        self.seed_partial(receipt=True, context_overrides={'mapping_code': 'b' * 64})
        self.assert_advice_withheld()

    def test_stale_model_pin_receipt_is_retained_without_unverified_advice(self):
        self.seed_partial(receipt=True, context_overrides={'model_digest': 'b' * 64})
        self.assert_advice_withheld()

    def test_verified_current_partial_candidates_need_no_embedding_or_model_on_get(self):
        self.seed_partial(receipt=True)
        before = list(self.revision.source_analyses.values_list('source_id', 'payload', 'digest'))
        with patch.object(mapping, '_semantic_vectors', side_effect=AssertionError('No retrieval on GET')) as vectors, \
                patch.object(mapping.evidence_pipeline, 'embed', side_effect=AssertionError('No embedding on GET')) as embed, \
                patch.object(mapping.local_ai, 'ollama', side_effect=AssertionError('No model on GET')) as model:
            result = self.qa_state()
        vectors.assert_not_called(); embed.assert_not_called(); model.assert_not_called()
        first = next(photo for photo in result['photos'] if photo['id'] == self.ids[0])
        self.assertEqual(first['photo_match']['status'], 'proposed')
        self.assertEqual(first['photo_match']['candidates'][0]['field_id'], 'manufacturer')
        self.assertEqual(next(photo for photo in result['photos'] if photo['id'] == self.ids[1])['photo_match']['status'], 'pending')
        self.assertFalse(any(item['accepted'] for item in result['items']))
        self.assertEqual(result['links'], [])
        self.assertEqual(list(self.revision.source_analyses.values_list('source_id', 'payload', 'digest')), before)


class MappingReceiptContractTests(SimpleTestCase):
    def receipt(self):
        analyses = [{'source_id': 'photo:17', 'model': 'synthetic-local-model', 'findings': [
            {'component': 'Cabinet manufacturer', 'value': 'SyntheticCo', 'confidence': 'high'}]}]
        schema = {'sections': [{'id': 'general', 'title': 'General', 'fields': [
            {'id': 'manufacturer', 'label': 'Cabinet manufacturer', 'type': 'text'}]}]}
        batch = list(mapping.mapping_batches(analyses, schema))[0]
        context = mapping.partial_mapping_context(analyses, schema, 'synthetic-local-model', 'a' * 64)
        result = mapping._with_candidates(batch, {'bindings': [
            {'finding_key': batch['findings'][0]['finding_key'], 'field_id': 'manufacturer',
             'reason': 'Actual source label.'}], 'unassigned': [],
             'identity': mapping.binding_identity(batch, context['model']), 'batch_identity': batch['identity']})
        return batch, context, mapping.with_partial_mapping_context(batch, result, context)

    def test_receipt_rejects_batch_binding_key_and_result_splicing(self):
        batch, context, saved = self.receipt()
        self.assertTrue(mapping.verified_partial_mapping(batch['key'], saved, context))
        for changes in [{'batch_identity': 'b' * 64}, {'identity': 'b' * 64},
                        {'photo_matches': [{'source_id': 'photo:17', 'reason': 'Forged result'}]}]:
            with self.subTest(changes=changes):
                self.assertFalse(mapping.verified_partial_mapping(batch['key'], {**saved, **changes}, context))
        self.assertFalse(mapping.verified_partial_mapping('mapping:0001', saved, context))

    def test_current_context_requires_the_actual_job_model_and_pin(self):
        batch, context, saved = self.receipt()
        for changes in [{'model': 'other-model'}, {'model_digest': 'b' * 64}, {'model_digest': ''},
                        {'mapping_version': 'obsolete'}]:
            with self.subTest(changes=changes):
                self.assertFalse(mapping.verified_partial_mapping(batch['key'], saved, {**context, **changes}))


@override_settings(**remote_fixtures.SETTINGS)
class RemoteMappingReceiptTests(remote_fixtures.Fixtures, TestCase):
    def test_remote_client_cannot_supply_a_trusted_projection_receipt(self):
        claimed = self.claim()
        for _ in range(2):
            task = bridge.next_task(self.credential, claimed['job_id'], claimed['lease'])
            self.assertEqual(task['kind'], 'source')
            result = self.analysed(task['input'], claimed['model'])
            for finding in result['findings']:
                finding['field_hint'] = ''
            self.complete(claimed, task, result)
        task = bridge.next_task(self.credential, claimed['job_id'], claimed['lease'])
        self.assertEqual(task['kind'], 'mapping')
        forged = {'bindings': [{'finding_key': finding['finding_key'],
            'field_id': 'manufacturer' if finding['category'] == 'equipment' else 'tower_height',
            'reason': 'Synthetic source property.'} for finding in task['input']['findings']],
            'unassigned': [], 'projection_context': {'model_digest': 'client-forged'},
            'photo_matches': [{'source_id': 'photo:999999', 'state': 'proposed'}]}
        self.complete(claimed, task, forged)
        saved = self.revision.source_analyses.get(source_id=task['input']['key'])
        job = self.revision.processing_job
        job.refresh_from_db()
        analyses = [entry.payload for entry in self.revision.source_analyses.exclude(source_id__startswith='mapping:')]
        context = mapping.partial_mapping_context(analyses, self.revision.snapshot['schema'], job.model, job.model_digest)
        self.assertTrue(mapping.verified_partial_mapping(saved.source_id, saved.payload, context))
        self.assertEqual(saved.payload['projection_context']['model_digest'], 'd' * 64)
        self.assertNotIn('client-forged', str(saved.payload))
        self.assertNotIn('photo:999999', str(saved.payload))
        before = (saved.payload, saved.digest)
        duplicate = self.complete(claimed, task, forged)
        self.assertTrue(duplicate['duplicate'])
        saved.refresh_from_db()
        self.assertEqual((saved.payload, saved.digest), before)
