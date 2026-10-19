"""Independent source-integrity, version identity and capture-stage regressions."""
import base64
import hashlib
import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import connection
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_evidence_learning as fixtures
from .models import Checklist, Project, ProjectMembership, PhotoJob, PhotoEvidence
from .evidence_models import EvidenceAnalysisRecord
from .evidence_learning import analysis_key, find_analysis, get_or_create_analysis, learning_access
from . import evidence_pipeline as pipeline


@override_settings(SECRET_KEY='isolated-evidence-integrity',ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EvidenceIntegrityTests(TestCase):
    person=fixtures.EvidenceLearningTests.person

    def setUp(self):
        fixtures.EvidenceLearningTests.setUp(self)
        folder=Path(__file__).resolve().parents[2]/'.local/tmp'
        folder.mkdir(exist_ok=True,parents=True)
        temporary=tempfile.TemporaryDirectory(dir=folder,prefix='evidence-integrity-')
        self.addCleanup(temporary.cleanup)
        storage=override_settings(MEDIA_ROOT=temporary.name)
        storage.enable();self.addCleanup(storage.disable)
        image=BytesIO();Image.new('RGB',(40,30),'green').save(image,format='PNG')
        self.raw=image.getvalue()
        self.photo.original.save('synthetic-original.png',ContentFile(self.raw))
        self.photo.sha256=hashlib.sha256(self.raw).hexdigest()
        self.photo.save(update_fields=['sha256'])
        self.context={**self.versions,'model_digest':'a'*64,'tool_fingerprint':'b'*64,
                      'release_id':None,'release_version':0}

    def test_cached_result_cannot_bypass_actual_original_tamper_guard(self):
        record,_=get_or_create_analysis(self.checklist,self.photo,{'drafts':[]},self.context)
        Path(self.photo.original.path).write_bytes(b'corrupt replacement bytes')
        with patch('core.photo_metadata.extract_metadata') as extract,patch('core.local_evidence_tools.extract_local_tools') as tools:
            with self.assertRaises(ValidationError):
                pipeline.analyze(self.photo,self.checklist.schema_snapshot,'synthetic',self.context,lambda:None,None)
        extract.assert_not_called();tools.assert_not_called()
        self.assertEqual(EvidenceAnalysisRecord.objects.count(),1)
        record.refresh_from_db();self.assertEqual(record.payload,{'drafts':[]})

    def test_uncached_corrupt_source_stops_before_observation_is_extracted_or_saved(self):
        Path(self.photo.original.path).write_bytes(b'tampered before first extraction')
        with patch('core.photo_metadata.extract_metadata') as extract:
            with self.assertRaises(ValidationError):
                pipeline.analyze(self.photo,self.checklist.schema_snapshot,'synthetic',self.context,lambda:None,None)
        extract.assert_not_called()
        self.photo.refresh_from_db();self.assertEqual(self.photo.analysis_signature,'')
        self.assertFalse(EvidenceAnalysisRecord.objects.exists())

    def test_targeted_check_derives_image_from_original_not_mutable_preview(self):
        self.photo.preview.name='missing-or-untrusted-preview.png'
        response={'assessments':[{'field_id':'base','outcome':'insufficient','reason':'Synthetic targeted response',
                                'visible_evidence':'','missing_evidence':['A closer original photograph']} ]}
        with patch('core.photo_service.verify_vision'),patch('core.photo_service.ollama',return_value={'message':{'content':json.dumps(response)}}) as native:
            result=pipeline.targeted_vision(self.photo,'synthetic',{'system':'Synthetic test','fields':[{'id':'base'}]},lambda:None)
        self.assertEqual(result,response)
        encoded=native.call_args.args[1]['messages'][1]['images'][0]
        actual=Image.open(BytesIO(base64.b64decode(encoded)))
        self.assertEqual(actual.size,(40,30))
        red,green,blue=actual.getpixel((20,15));self.assertGreater(green,red+40);self.assertGreater(green,blue+40)

    def test_source_metadata_group_and_each_exact_version_change_cache_identity(self):
        original=analysis_key(self.checklist,self.photo,self.context)
        for key,value in self.context.items():
            changed={**self.context,key:('changed-'+str(value))}
            self.assertNotEqual(original,analysis_key(self.checklist,self.photo,changed),key)
        self.photo.metadata={'gps':{'latitude':24,'longitude':46}}
        self.assertNotEqual(original,analysis_key(self.checklist,self.photo,self.context))
        self.photo.metadata={};self.photo.group='Electrical'
        self.assertNotEqual(original,analysis_key(self.checklist,self.photo,self.context))

    def test_tampered_saved_payload_is_rejected_and_never_silently_replaced(self):
        record,_=get_or_create_analysis(self.checklist,self.photo,{'drafts':[]},self.context)
        # Raw corruption simulation bypasses immutable ORM only inside this test DB.
        with connection.cursor() as cursor:
            cursor.execute('UPDATE core_evidenceanalysisrecord SET payload=%s WHERE id=%s',[json.dumps({'drafts':['tampered']}),record.pk])
        with self.assertRaises(ValidationError):find_analysis(self.checklist,self.photo,self.context)
        with self.assertRaises(ValidationError):get_or_create_analysis(self.checklist,self.photo,{'drafts':[]},self.context)
        self.assertEqual(EvidenceAnalysisRecord.objects.count(),1)

    def test_pinned_model_or_tool_changes_require_explicit_adoption(self):
        with patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            original=pipeline.processing_context(self.checklist,'synthetic-model')
        PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,model='synthetic-model',
                                schema=self.checklist.schema_snapshot,progress={'evidence_context':original})
        with patch.object(pipeline,'model_fingerprint',return_value='c'*64),patch.object(pipeline,'tool_fingerprint',return_value='b'*64):
            with self.assertRaises(ValidationError):pipeline.processing_context(self.checklist,'synthetic-model')
            adopted=pipeline.processing_context(self.checklist,'synthetic-model',adopt=True)
            self.assertEqual(adopted['model_digest'],'c'*64)
        with patch.object(pipeline,'model_fingerprint',return_value='a'*64),patch.object(pipeline,'tool_fingerprint',return_value='d'*64):
            with self.assertRaises(ValidationError):pipeline.processing_context(self.checklist,'synthetic-model')

    def test_additional_project_quality_access_works_but_revoke_and_foreign_site_do_not(self):
        project=Project.objects.create(name='Additional scoped project',company=self.company,checklist_template=self.template)
        site=Checklist.objects.create(project=project,user=self.engineer,quality_reviewer=self.quality,site_id='ADDITIONAL')
        membership=ProjectMembership.objects.create(user=self.quality,project=project,is_active=True)
        self.assertEqual(learning_access(self.quality,site.pk).pk,site.pk)
        membership.is_active=False;membership.save()
        with self.assertRaises(Http404):learning_access(self.quality,site.pk)
        foreign=Checklist.objects.create(project=self.project,user=self.lead,quality_reviewer=self.other_quality,site_id='OTHER-OWNER')
        with self.assertRaises(Http404):learning_access(self.engineer,foreign.pk)
        with self.assertRaises(Http404):learning_access(self.quality,foreign.pk)

    def test_active_analysis_blocks_legacy_submit_and_cannot_be_bypassed_by_unrequired_fields(self):
        job=PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,model='synthetic',
                                   schema=self.checklist.schema_snapshot,status='running')
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(reverse('custom_checklist_submit',args=[self.checklist.pk])).status_code,302)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.status,Checklist.Status.DRAFT)
        from .template_service import missing_required
        self.assertTrue(any('analysis is still active' in label for label in missing_required(self.checklist)))
        job.status='completed';job.save()
        self.assertFalse(missing_required(self.checklist))

    def test_active_analysis_blocks_independent_revision_before_any_signature(self):
        from .independent_workflow import configure_policy,submit_revision
        from .roadmap_service import qualify_template
        self.checklist.coordinate_reference={'source':'Synthetic original','crs':'WGS84'}
        self.checklist.save()
        qualify_template(self.lead,self.project,self.checklist.workflow_type,'Synthetic criteria','Synthetic method','Explicit test applicability')
        configure_policy(self.admin,self.checklist,self.quality,self.lead,'Synthetic explicit reviewers',customer_required=False)
        self.checklist.refresh_from_db()
        PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,model='synthetic',
                                schema=self.checklist.schema_snapshot,status='queued')
        with self.assertRaises(ValidationError):submit_revision(self.engineer,self.checklist)
        self.assertFalse(self.checklist.submission_revisions.exists())

    def test_scoped_admin_manual_mapping_captures_pending_case_without_internal_learning_access(self):
        from .field_photo_service import schema_digest
        from .evidence_models import EvidenceCorrection
        self.client.force_login(self.admin)
        response=self.client.post(reverse('photo_mapping',args=[self.checklist.pk]),
            data=json.dumps({'expected_schema_digest':schema_digest(self.checklist),
                             'decisions':[{'photo_id':self.photo.pk,'field_id':'base','action':'manual'}]}),
            content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        case=EvidenceCorrection.objects.get(checklist=self.checklist,captured_by=self.admin)
        self.assertEqual(case.action,'manual')
        self.assertFalse(hasattr(case,'peer_decision'))
        self.assertEqual(self.client.get(reverse('evidence_learning_state',args=[self.checklist.pk])).status_code,403)

    def test_quality_approval_cannot_race_active_analysis_but_return_remains_available(self):
        from .quality_workflow import review_quality
        self.checklist.status=Checklist.Status.SUBMITTED
        self.checklist.save()
        PhotoJob.objects.create(checklist=self.checklist,requested_by=self.engineer,model='synthetic',
                                schema=self.checklist.schema_snapshot,status='running')
        with self.assertRaises(ValidationError):
            review_quality(self.quality,self.checklist,'approve','QC attempted during worker',self.checklist.updated_at.isoformat())
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.SUBMITTED)
        self.assertEqual(self.checklist.quality_approval,{})
        review_quality(self.quality,self.checklist,'reject','Return for correction while analysis finishes',self.checklist.updated_at.isoformat())
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.status,Checklist.Status.REJECTED)
