"""Independent source-reuse guards; ordinary tests never invoke a native model.

The worker-call-count test isolates inference to prove safe cache invalidation.
Real native throughput and extraction remain a separate explicitly run check.
"""
import base64
import hashlib
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, ImageDraw, ImageEnhance

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .models import Checklist, PhotoEvidence
from .survey_acceleration import ObservationReuse, analysis_identity, photo_duplicates
from .survey_evidence import extract_sources
from .survey_processing_models import SurveyProcessingJob, SurveyProcessingRevision, SurveySourceAnalysis


def patterned_image():
    image = Image.new('RGB', (120, 90), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 8, 75, 65), fill=(35, 45, 60))
    draw.line((15, 70, 105, 20), fill=(160, 30, 30), width=4)
    return image


def png_bytes(image, compression=6):
    output = BytesIO()
    image.save(output, 'PNG', compress_level=compression)
    return output.getvalue()


def source_fixture():
    raw = png_bytes(patterned_image())
    source = next(extract_sources([{'id': 1, 'filename': 'SYNTHETIC-cache-photo.png',
        'sha256': hashlib.sha256(raw).hexdigest(), 'raw': raw,
        'metadata': {'recorded_coordinates': [24, 46]}}], []))
    source['field_catalog'] = [{'id': 'manufacturer', 'label': 'Manufacturer', 'type': 'text'}]
    source.update(schema_digest='d' * 64, template_id=7)
    return source


class IndependentReuseIdentityTests(SimpleTestCase):
    def test_actual_image_context_reference_and_schema_changes_are_not_reusable(self):
        source = source_fixture()
        signature = analysis_identity(source, 'a' * 64)
        variants = [
            {'metadata': {**source['metadata'], 'recorded_coordinates': [25, 47]}},
            {'reference': 'targeted crop 1'},
            {'source_type': 'document_image'},
            {'text': 'SYNTHETIC recorded reference: 2 m'},
            {'field_catalog': [{'id': 'other_stable_id', 'label': 'Manufacturer', 'type': 'text'}]},
            {'schema_digest': 'e' * 64},
            {'template_id': 8},
            {'image_b64': base64.b64encode(png_bytes(Image.new('RGB', (120, 90), 'blue'))).decode()},
        ]
        for changed in variants:
            with self.subTest(changed=list(changed)):
                self.assertNotEqual(analysis_identity({**source, **changed}, 'a' * 64), signature)
        self.assertNotEqual(analysis_identity(source, 'b' * 64), signature)

    def test_extraction_prompt_and_version_changes_invalidate_old_observations(self):
        source = source_fixture()
        signature = analysis_identity(source, 'a' * 64)
        with patch('core.survey_evidence.SYSTEM_PROMPT', 'SYNTHETIC changed extraction rules'):
            self.assertNotEqual(analysis_identity(source, 'a' * 64), signature)
        with patch('core.survey_evidence.EXTRACTION_VERSION', 'SYNTHETIC-next-extraction'):
            self.assertNotEqual(analysis_identity(source, 'a' * 64), signature)


@override_settings(SECRET_KEY='independent-resume-acceleration', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IndependentReuseIntegrationTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    request = fixtures.SurveyProcessingTests.request
    add_photo = fixtures.SurveyProcessingTests.add_photo
    analysed = fixtures.SurveyProcessingTests.analysed
    processing = fixtures.SurveyProcessingTests.processing

    def revision(self, checklist=None, number=1, model='a' * 64):
        checklist = checklist or self.checklist
        snapshot = pipeline.freeze_data(checklist)
        snapshot['independent_fixture_number'] = number
        revision = SurveyProcessingRevision.objects.create(checklist=checklist, number=number,
            digest=pipeline.digest(snapshot), snapshot=snapshot, submitted_by=self.engineer)
        SurveyProcessingJob.objects.create(revision=revision, model='qwen3.5:4b', model_digest=model)
        return revision

    def store(self, revision, source, **extra):
        payload = {'source_id': source['source_id'], 'source_type': source['source_type'],
            'reference': source['reference'], 'sha256': source['sha256'],
            'verification_status': 'needs_review', 'findings': [], **extra}
        payload = ObservationReuse(revision, 'a' * 64).stamp(source, payload)
        return SurveySourceAnalysis.objects.create(revision=revision, source_id=source['source_id'],
            payload=payload, digest=pipeline.digest(payload))

    def test_same_model_input_from_another_task_is_not_a_reuse_candidate(self):
        source = source_fixture()
        prior = self.revision()
        self.store(prior, source)
        other = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-OTHER-CACHE-SITE',
            schema_snapshot=deepcopy(self.schema))
        foreign = self.revision(other)
        self.assertIsNone(ObservationReuse(foreign, 'a' * 64).lookup(source))
        current = self.revision(number=2)
        self.assertIsNotNone(ObservationReuse(current, 'a' * 64).lookup(source))
        self.assertIsNone(ObservationReuse(current, 'b' * 64).lookup(source))

    def test_reuse_references_new_source_and_never_inherits_acceptance(self):
        source = source_fixture()
        prior = self.revision()
        original = self.store(prior, source, accepted=True, findings=[{
            'source_id': source['source_id'], 'finding_key': source['source_id'] + ':finding:7',
            'field_hint': 'manufacturer', 'value': 'SYNTHETIC reported maker', 'unit': '',
            'basis': 'recorded', 'evidence_quote': 'SYNTHETIC reported maker',
            'confidence': 'high', 'verification_status': 'needs_review', 'accepted': True, 'measured': True}])
        current = self.revision(number=2)
        cloned_source = {**source, 'source_id': 'photo:999', 'sha256': 'c' * 64}
        with patch('core.survey_evidence.analyse_source') as native:
            cloned = ObservationReuse(current, 'a' * 64).lookup(cloned_source)
        native.assert_not_called()
        self.assertEqual(cloned['source_id'], 'photo:999')
        self.assertEqual(cloned['sha256'], 'c' * 64)
        self.assertNotIn('accepted', cloned)
        self.assertEqual(cloned['findings'][0]['source_id'], 'photo:999')
        self.assertEqual(cloned['findings'][0]['finding_key'], 'photo:999:finding:7')
        self.assertNotIn('accepted', cloned['findings'][0])
        self.assertFalse(cloned['findings'][0]['measured'])
        self.assertEqual(cloned['findings'][0]['verification_status'], 'needs_review')
        self.assertEqual(cloned['acceleration']['reused_from'],
                         {'revision_id': prior.pk, 'revision_number': prior.number,
                          'source_id': source['source_id']})
        original.refresh_from_db()
        self.assertTrue(original.payload['accepted'])
        self.assertEqual(original.digest, pipeline.digest(original.payload))

    def test_changed_recorded_metadata_reprocesses_only_the_changed_source(self):
        first, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        stack, first_native, _ = self.processing()
        self.assertTrue(pipeline.process_next())
        self.assertEqual(first_native.call_count, 2)
        stack.close()
        saved = {row.pk: row.digest for row in first.source_analyses.all()}
        self.photo.metadata = {**self.photo.metadata, 'independent_capture_note': 'Different recorded context'}
        self.photo.save(update_fields=['metadata'])
        second, _ = pipeline.submit(self.request(), self.checklist.pk, True)
        stack, native, _ = self.processing()
        self.assertTrue(pipeline.process_next())
        self.assertEqual(native.call_count, 1, 'Only byte-identical AND context-identical inputs may skip inference')
        self.assertEqual(second.source_analyses.count(), 2)
        # SQLite distinguishes a JSON null from an absent JSON path; inspect
        # the actual saved provenance rather than treating key existence as reuse.
        self.assertEqual(sum(row.payload['acceleration']['reused_from'] is not None
                             for row in second.source_analyses.all()), 1)
        self.assertEqual({row.pk: row.digest for row in first.source_analyses.all()}, saved)
        self.assertFalse(any(item.get('accepted') for item in second.processing_result.payload['checklist_items']))
        stack.close()

    def test_reuse_search_is_bounded_to_twenty_retained_revisions(self):
        source = source_fixture()
        first = self.revision()
        self.store(first, source)
        for number in range(2, 23):
            current = self.revision(number=number)
        self.assertIsNone(ObservationReuse(current, 'a' * 64).lookup(source))

    def test_exact_and_possible_duplicates_are_advisory_and_keep_originals(self):
        image = patterned_image()
        near = ImageEnhance.Brightness(image).enhance(1.02)
        records = []
        originals = {}
        for index, raw in enumerate([png_bytes(image, 0), png_bytes(image, 9), png_bytes(near)], 1):
            photo = PhotoEvidence.objects.create(checklist=self.checklist, uploaded_by=self.engineer,
                filename=f'SYNTHETIC-duplicate-{index}.png', sha256=hashlib.sha256(raw).hexdigest())
            photo.original.save(photo.filename, ContentFile(raw))
            originals[photo.pk] = (photo.original.path, raw)
            records.append({'id': photo.pk, 'filename': photo.filename, 'sha256': photo.sha256, 'raw': raw})
        self.assertNotEqual(records[0]['raw'], records[1]['raw'])
        revision = self.revision()
        sources = list(extract_sources(records, []))
        for index, source in enumerate(sources):
            source['field_catalog'] = []
            if index == 2:
                self.assertIsNone(ObservationReuse(revision, 'a' * 64).lookup(source),
                                  'A similar photo must still receive its own analysis')
            self.store(revision, source)
        annotations = photo_duplicates(revision)
        self.assertIsNone(annotations[records[0]['id']]['duplicate'])
        self.assertEqual(annotations[records[1]['id']]['duplicate']['kind'], 'exact')
        self.assertEqual(annotations[records[1]['id']]['duplicate']['photo_id'], records[0]['id'])
        self.assertEqual(annotations[records[2]['id']]['duplicate']['kind'], 'possible')
        self.assertIsNone(annotations[records[2]['id']]['analysis_reused'])
        self.assertEqual(self.checklist.photo_evidence.count(), 5)
        self.assertEqual(revision.snapshot, SurveyProcessingRevision.objects.get(pk=revision.pk).snapshot)
        for filename, raw in originals.values():
            with open(filename, 'rb') as handle:
                self.assertEqual(handle.read(), raw)
