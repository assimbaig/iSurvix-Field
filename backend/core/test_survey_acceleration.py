"""Reuse only identical model inputs; similar photos remain independent evidence."""
import base64
import json
from copy import deepcopy
from io import BytesIO

from django.test import SimpleTestCase, TestCase, override_settings
from django.core.files.base import ContentFile
import hashlib
from unittest.mock import patch
from PIL import Image, ImageDraw

from . import test_survey_processing as fixture, survey_processing as pipeline
from .survey_processing_models import SurveyProcessingJob


class AnalysisIdentityTests(SimpleTestCase):
    def source(self):
        return {'source_id':'photo:1','source_type':'photo','sha256':'a'*64,'reference':'original',
            'text':'','image_b64':base64.b64encode(b'validated-image-content').decode(),
            'metadata':{'recorded_coordinates':[24,46]},
            'field_catalog':[{'id':'brand','label':'Manufacturer','type':'text'}]}

    def test_reuse_identity_binds_image_context_schema_and_model_but_not_database_ids(self):
        from .survey_acceleration import analysis_identity
        source=self.source();first=analysis_identity(source,'model-pin-a')
        same={**source,'source_id':'photo:999','sha256':'b'*64}
        self.assertEqual(analysis_identity(same,'model-pin-a'),first)
        for change in [{'image_b64':base64.b64encode(b'other-image').decode()},
                       {'metadata':{'recorded_coordinates':[25,47]}},
                       {'field_catalog':[{'id':'different','label':'Manufacturer','type':'text'}]},
                       {'schema_digest':'different approved requirements'},
                       {'template_id':777},
                       {'text':'Recorded dimension: 3 m'}]:
            self.assertNotEqual(analysis_identity({**source,**change},'model-pin-a'),first)
        self.assertNotEqual(analysis_identity(source,'model-pin-b'),first)
        with patch('core.survey_evidence.INFERENCE_OPTIONS',{'temperature':.2,'num_ctx':12288},create=True):
            self.assertNotEqual(analysis_identity(source,'model-pin-a'),first)

    def test_exact_visual_fingerprint_distinguishes_changed_pixels(self):
        from .survey_acceleration import visual_fingerprint
        first=Image.new('RGB',(80,60),'white');ImageDraw.Draw(first).rectangle((5,5,30,30),fill='black')
        same=first.copy();changed=first.copy();changed.putpixel((70,50),(255,0,0))
        a=visual_fingerprint(first);b=visual_fingerprint(same);c=visual_fingerprint(changed)
        self.assertEqual(a['pixels_sha256'],b['pixels_sha256'])
        self.assertNotEqual(a['pixels_sha256'],c['pixels_sha256'])
        self.assertEqual(len(a['dhash']),16)


class CompactResponseTests(SimpleTestCase):
    def test_compact_wire_preserves_every_required_observation_and_stable_field_id(self):
        from .survey_evidence import decode_observation_response, observation_response_schema
        raw={'f':[{'f':'height','c':'measurement','s':'Recorded cabinet height','v':2,'u':'m',
                   'b':'recorded','q':'Recorded cabinet height: 2 m','p':'high','n':'Readable label'}],
             'm':['Mounting detail is missing'],'x':[],'a':[]}
        parsed=decode_observation_response(json.dumps(raw))
        self.assertEqual(parsed.findings[0].field_hint,'height')
        self.assertEqual(parsed.findings[0].value,2)
        self.assertEqual(parsed.findings[0].evidence_quote,'Recorded cabinet height: 2 m')
        self.assertEqual(parsed.findings[0].unit,'m')
        self.assertEqual(parsed.missing,['Mounting detail is missing'])
        schema=observation_response_schema([{'id':'height'}],compact=True)
        observation=schema['$defs']['Observation']
        self.assertEqual(set(observation['required']),set(raw['f'][0]))
        self.assertEqual(observation['properties']['f']['enum'],['','height'])
        self.assertFalse(observation['additionalProperties'])

    def test_compact_decoder_rejects_missing_context_repeated_keys_and_unknown_values(self):
        from .survey_evidence import decode_observation_response, EvidenceError
        variants=[{'f':[{'c':'equipment','v':'Cabinet','b':'visible','p':'high'}],'m':[],'x':[],'a':[]},
                  {'f':[],'m':[],'x':[],'a':[],'invented':'approved'}]
        for value in variants:
            with self.assertRaises(EvidenceError): decode_observation_response(json.dumps(value))
        with self.assertRaises(EvidenceError):decode_observation_response('{"f":[],"f":[],"m":[],"x":[],"a":[]}')

    def test_retained_canonical_contract_stays_strict_and_compatible(self):
        from .survey_evidence import decode_observation_response
        self.assertEqual(decode_observation_response('{"findings":[],"missing":[]}').findings,[])


@override_settings(SECRET_KEY='isolated-acceleration-tests',ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AnalysisReuseIntegrationTests(TestCase):
    setUp=fixture.SurveyProcessingTests.setUp
    person=fixture.SurveyProcessingTests.person
    request=fixture.SurveyProcessingTests.request
    add_photo=fixture.SurveyProcessingTests.add_photo
    analysed=fixture.SurveyProcessingTests.analysed
    processing=fixture.SurveyProcessingTests.processing

    def test_new_revision_reuses_unchanged_raw_observations_without_reusing_human_decisions(self):
        from .models import Checklist
        original=self.checklist
        other=Checklist.objects.create(project=self.project,user=self.engineer,quality_reviewer=self.quality,
            site_id='SYNTHETIC-UNRELATED-REVISION-ALLOCATION',answer_data={'custom':{'contact':'Other site'}})
        self.checklist=other;self.add_photo('red')
        pipeline.submit(self.request(),other.pk,True)
        setup,_,_=self.processing();self.assertTrue(pipeline.process_next());setup.close()
        self.checklist=original
        first,_=pipeline.submit(self.request(),self.checklist.pk,True)
        self.assertNotEqual(first.pk,first.number)
        stack,model,_=self.processing();self.assertTrue(pipeline.process_next())
        self.assertEqual(model.call_count,2);stack.close()
        old={row.pk:row.digest for row in first.source_analyses.all()}
        self.checklist.answer_data={'custom':{'contact':'Changed reported survey contact'}}
        self.checklist.save(update_fields=['answer_data'])
        second,_=pipeline.submit(self.request(),self.checklist.pk,True)
        _,model,_=self.processing();self.assertTrue(pipeline.process_next())
        job=SurveyProcessingJob.objects.get(revision=second)
        self.assertEqual(job.status,'ready_for_review',job.error)
        self.assertEqual(model.call_count,0,'Unchanged actual inputs must not be inferred twice')
        self.assertEqual(second.source_analyses.count(),2)
        for row in second.source_analyses.all():
            self.assertEqual(row.payload['acceleration']['reused_from']['revision_id'],first.pk)
            self.assertEqual(row.payload['acceleration']['reused_from'].get('revision_number'),first.number)
            self.assertEqual(row.payload['source_id'],row.source_id)
            self.assertEqual(row.payload.get('performance',{}).get('requests'),0)
            self.assertTrue(row.payload['performance']['cache_hit'])
        self.assertEqual({row.pk:row.digest for row in first.source_analyses.all()},old)
        self.assertFalse(any(item.get('accepted') for item in second.processing_result.payload['checklist_items']))

    def test_cache_never_crosses_checklist_or_model_boundary_and_detects_corruption(self):
        from .survey_acceleration import ObservationReuse,analysis_identity
        from .survey_processing_models import SurveySourceAnalysis
        from django.core.exceptions import ValidationError
        first,_=pipeline.submit(self.request(),self.checklist.pk,True)
        source=AnalysisIdentityTests().source();key=analysis_identity(source,'m'*64)
        payload={'source_id':'photo:1','findings':[],'acceleration':{'identity':key}}
        SurveySourceAnalysis.objects.create(revision=first,source_id='photo:1',payload=payload,digest='wrong')
        SurveyProcessingJob.objects.filter(revision=first).update(model_digest='m'*64)
        cache=ObservationReuse(first,'m'*64)
        with self.assertRaises(ValidationError):cache.lookup(source)
        self.assertIsNone(ObservationReuse(first,'n'*64).lookup(source))

    def test_cached_resubmission_finishes_even_when_gpu_inference_lease_is_busy(self):
        from .local_ai import InferenceBusy
        first,_=pipeline.submit(self.request(),self.checklist.pk,True)
        setup,_,_=self.processing();self.assertTrue(pipeline.process_next());setup.close()
        self.checklist.answer_data={'custom':{'contact':'New reported contact; identical evidence'}}
        self.checklist.save(update_fields=['answer_data'])
        second,_=pipeline.submit(self.request(),self.checklist.pk,True)
        setup,model,_=self.processing()
        with patch('core.photo_queue.photo_inference_lease',side_effect=InferenceBusy('GPU is processing another task')):
            self.assertTrue(pipeline.process_next())
        job=SurveyProcessingJob.objects.get(revision=second)
        self.assertEqual(job.status,'ready_for_review',job.error)
        self.assertEqual(model.call_count,0)
        self.assertEqual(second.source_analyses.count(),2)

    def test_retained_legacy_analyses_gain_duplicate_tags_without_rewriting_or_reinferring(self):
        from .models import PhotoEvidence
        from . import survey_evidence
        from .survey_processing_models import SurveySourceAnalysis
        from .survey_acceleration import photo_duplicates
        stream=BytesIO();Image.new('RGB',(60,40),'blue').save(stream,'PNG',compress_level=1)
        raw=stream.getvalue()
        duplicate=PhotoEvidence.objects.create(checklist=self.checklist,uploaded_by=self.engineer,
            filename='same-pixels-different-file.png',sha256=hashlib.sha256(raw).hexdigest())
        duplicate.original.save(duplicate.filename,ContentFile(raw))
        revision,_=pipeline.submit(self.request(),self.checklist.pk,True)
        records=[{**row,'path':PhotoEvidence.objects.get(pk=row['id']).original.path} for row in revision.snapshot['photos']]
        for source in survey_evidence.extract_sources(records,[]):
            payload=self.analysed(source,'qwen3.5:4b')
            SurveySourceAnalysis.objects.create(revision=revision,source_id=source['source_id'],
                payload=payload,digest=pipeline.digest(payload))
        before={row.pk:row.digest for row in revision.source_analyses.all()}
        _,model,_=self.processing();self.assertTrue(pipeline.process_next())
        self.assertEqual(model.call_count,0)
        self.assertEqual({row.pk:row.digest for row in revision.source_analyses.all()},before)
        annotations=photo_duplicates(revision)
        self.assertEqual(annotations[duplicate.pk]['duplicate']['kind'],'exact')
        self.assertEqual(annotations[duplicate.pk]['duplicate']['photo_id'],self.photo.pk)
        self.assertEqual(revision.processing_events.filter(action='source_fingerprints').count(),1)
