"""Disposable evidence pipeline integration; no native inference or live media."""
import tempfile
import hashlib
import json
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_evidence_learning as fixtures
from .evidence_models import EvidenceAnalysisRecord, EvidenceRuleRelease
from .evidence_learning import digest, get_or_create_analysis, learning_access
from .photo_models import PhotoJob, PhotoPlacement
from . import evidence_pipeline as pipeline


class EvidencePipelineTests(TestCase):
    person = fixtures.EvidenceLearningTests.person

    def setUp(self):
        fixtures.EvidenceLearningTests.setUp(self)
        temporary_root=Path(__file__).resolve().parents[2]/'.local'/'tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        self.media = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.photo.original.save('synthetic.png', ContentFile(b'isolated mocked source'))
        self.photo.sha256=hashlib.sha256(b'isolated mocked source').hexdigest()
        self.photo.save(update_fields=['sha256'])
        self.context = {'rules_version':'rules-1','model_version':'synthetic-model',
            'model_digest':'a'*64,'tool_version':'tools-1','tool_fingerprint':'b'*64,
            'prompt_version':'prompt-1','release_id':None,'release_version':0,'release_digest':digest([])}

    def pin(self, context=None):
        return PhotoJob.objects.create(checklist=self.checklist, requested_by=self.engineer,
            model='synthetic-model', schema=self.checklist.schema_snapshot,
            progress={'evidence_context':context or self.context})

    def test_saved_cache_reused_across_authorized_actors_without_inference(self):
        record, _ = get_or_create_analysis(self.checklist,self.photo,{'drafts':[], 'assessments':[]},self.context)
        with patch('core.photo_metadata.extract_metadata') as vision, patch.object(pipeline,'model_fingerprint',return_value='a'*64) as model, patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            for actor in [self.engineer,self.quality,self.lead]:
                allowed=learning_access(actor,self.checklist.pk)
                self.assertEqual(allowed.pk,self.checklist.pk)
                self.assertEqual(pipeline.analyze(self.photo,self.checklist.schema_snapshot,'synthetic-model',self.context,lambda:None,None),[])
            vision.assert_not_called()
            model.assert_not_called()
        self.assertEqual(EvidenceAnalysisRecord.objects.count(),1)
        self.assertEqual(pipeline.saved_state(self.checklist)['records'][0]['id'],record.pk)

    def test_changed_pinned_model_or_tools_fail_safe_without_adoption(self):
        self.pin()
        for model,tools in [('c'*64,'b'*64),('a'*64,'d'*64)]:
            with patch.object(pipeline,'model_fingerprint',return_value=model),patch.object(pipeline,'tool_fingerprint',return_value=tools):
                with self.assertRaises(ValidationError):pipeline.processing_context(self.checklist,'synthetic-model')
        self.assertEqual(EvidenceAnalysisRecord.objects.count(),0)

    def test_new_release_requires_explicit_adoption_and_keeps_old_context(self):
        self.pin()
        release=EvidenceRuleRelease.objects.create(project=self.project,version=1,references=[],digest=digest([]),published_by=self.lead,reason='Synthetic explicit release')
        with patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            self.assertEqual(pipeline.processing_context(self.checklist,'synthetic-model')['release_version'],0)
            adopted=pipeline.processing_context(self.checklist,'synthetic-model',adopt=True)
        self.assertEqual(adopted['release_id'],release.pk)
        self.assertEqual(adopted['release_version'],1)
        self.assertEqual(pipeline.latest_context(self.checklist),self.context)
        self.assertTrue(pipeline.saved_state(self.checklist)['update_available'])

    def test_actual_analysis_records_results_without_changing_human_evidence_or_answers(self):
        human=PhotoPlacement.objects.create(photo=self.photo,field_id='base',section_id='general',status='manual',reviewed_by=self.engineer,reason='Human choice')
        self.checklist.answer_data={'base':'Human answer'}
        self.checklist.save(update_fields=['answer_data'])
        observation={'caption':'Concrete tower foundation visible in synthetic evidence.','objects':['foundation'],'visible_text':[],'issues':[],'uncertainties':[]}
        with ExitStack() as stack:
            for owner,name,value in [(pipeline,'model_fingerprint','a'*64),(pipeline,'tool_fingerprint','b'*64)]:stack.enter_context(patch.object(owner,name,return_value=value))
            extract=stack.enter_context(patch('core.photo_metadata.extract_metadata',return_value=observation))
            stack.enter_context(patch('core.local_evidence_tools.extract_local_tools',return_value={}))
            stack.enter_context(patch('core.local_evidence_tools.semantic_similarities',return_value={}))
            stack.enter_context(patch('core.evidence_rules.evaluate_evidence',return_value=[{'field_id':'base','outcome':'insufficient','reasons':['Need clearer evidence'],'missing_evidence':['Overview photo']}]))
            stack.enter_context(patch('core.evidence_rules.verify_shortlist',return_value=[]))
            result=pipeline.analyze(self.photo,self.checklist.schema_snapshot,'synthetic-model',self.context,lambda:None,None)
            self.assertEqual(result,[])
            extract.assert_called_once()
        human.refresh_from_db();self.checklist.refresh_from_db()
        self.assertEqual(human.status,'manual')
        self.assertEqual(human.reason,'Human choice')
        self.assertEqual(self.checklist.answer_data,{'base':'Human answer'})
        self.assertEqual(self.checklist.section_approvals,{})
        saved=pipeline.saved_state(self.checklist,can_apply=True)
        self.assertEqual(saved['records'][0]['payload']['assessments'][0]['outcome'],'insufficient')
        self.assertTrue(saved['can_apply'])

    def test_current_schema_saved_state_hides_old_schema_records(self):
        get_or_create_analysis(self.checklist,self.photo,{'drafts':[]},self.context)
        self.checklist.schema_snapshot['sections'][0]['fields'][0]['label']='Changed checkpoint wording'
        self.checklist.save(update_fields=['schema_snapshot'])
        self.assertEqual(pipeline.saved_state(self.checklist)['records'],[])

    def test_photo_state_exposes_same_saved_assessment_for_each_authorized_actor(self):
        record,_=get_or_create_analysis(self.checklist,self.photo,{'drafts':[], 'assessments':[
            {'field_id':'base','outcome':'insufficient','reasons':['Missing overview']} ]},self.context)
        results=[]
        for actor in [self.engineer,self.quality,self.lead]:
            self.client.force_login(actor)
            response=self.client.get(reverse('photo_state',args=[self.checklist.pk]))
            self.assertEqual(response.status_code,200)
            results.append(response.json()['evidence_analysis']['records'])
        self.assertEqual(results[0],results[1])
        self.assertEqual(results[1],results[2])
        self.assertEqual(results[0][0]['id'],record.pk)

    def test_enqueue_adopts_published_release_only_after_explicit_apply(self):
        previous=self.pin();previous.status='completed';previous.save(update_fields=['status'])
        release=EvidenceRuleRelease.objects.create(project=self.project,version=1,references=[],digest=digest([]),published_by=self.lead,reason='Explicit synthetic release')
        self.client.force_login(self.engineer)
        with patch('core.photo_views.verify_vision'),patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            normal=self.client.post(reverse('photo_enqueue',args=[self.checklist.pk]),json.dumps({'photo_ids':[self.photo.pk],'model':'synthetic-model'}),content_type='application/json')
            self.assertEqual(normal.status_code,201,normal.content)
            normal_job=PhotoJob.objects.get(pk=normal.json()['id'])
            self.assertEqual(normal_job.progress['evidence_context']['release_version'],0)
            normal_job.status='completed';normal_job.save(update_fields=['status'])
            adopted=self.client.post(reverse('photo_enqueue',args=[self.checklist.pk]),json.dumps({'photo_ids':[self.photo.pk],'model':'synthetic-model','apply_current_rules':True}),content_type='application/json')
            self.assertEqual(adopted.status_code,201,adopted.content)
        adopted_job=PhotoJob.objects.get(pk=adopted.json()['id'])
        self.assertEqual(adopted_job.progress['evidence_context']['release_id'],release.pk)
        self.assertEqual(adopted_job.progress['evidence_context']['release_version'],1)
