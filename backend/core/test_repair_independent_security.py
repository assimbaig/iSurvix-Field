"""Independent post-functional repair security regressions.

Originally executed by the separate read-only AppSec reviewer. All records,
metadata services and deliberate corruption are isolated synthetic fixtures;
run with scripts/run_backend_tests.py, never operational evidence.
"""
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from core import survey_pause as pause, survey_checklist_mapping as mapping, qa_matching
from core import test_pause_command_generation as controls
from core import test_matching_readiness_repairs as matching
from core import test_document_repair_regressions as documents
from core import test_progress_revision_repair as progress_fixture
from core.survey_processing_models import SurveySourceAnalysis, SurveyDocument

@override_settings(SECRET_KEY='independent-pr21-appsec',ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ControlAdversarialTests(controls.PauseCommandGenerationTests):
    # Keep independent probe count separate from inherited functional cases.
    def test_foreign_actor_token_is_denied_even_when_generation_is_current(self):
        self.begin(); original=self.token()
        other=self.person('adversary_qa','QUALITY_ENGINEER')
        forged=pause._token(SimpleNamespace(user=other),self.revision,0)
        before=list(self.revision.processing_events.values_list('pk',flat=True))
        response=self.send('pause',forged)
        self.assertEqual(response.status_code,409)
        self.assertEqual(list(self.revision.processing_events.values_list('pk',flat=True)),before)
        self.assertEqual(self.send('pause',original).status_code,200)
    def test_cross_revision_and_boolean_generation_signed_tokens_are_denied(self):
        self.begin()
        signer=signing.Signer(salt=pause.CONTROL_SALT)
        good={'revision':self.revision.pk,'source':self.revision.digest,'actor':self.quality.pk,'generation':0}
        for mutate in [{'revision':self.revision.pk+100},{'source':'0'*64},{'generation':False},{'generation':-1}]:
            with self.subTest(mutate=mutate):
                response=self.send('pause',signer.sign_object({**good,**mutate},compress=True))
                self.assertEqual(response.status_code,409)
    def test_two_full_cycles_do_not_resurrect_any_previous_control_token(self):
        self.begin(); old=[]
        for i in range(2):
            old.append(('pause',self.token()));self.assertEqual(self.send(*old[-1]).status_code,200)
            old.append(('resume',self.token()));self.assertEqual(self.send(*old[-1]).status_code,200)
        self.assertEqual(self.send('pause',self.token()).status_code,200)
        for action, token in old:
            self.assertEqual(self.send(action,token).status_code,409)

@override_settings(SECRET_KEY='independent-pr21-appsec',ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MappingAdversarialTests(matching.PartialMappingContextTests):
    def test_receipt_does_not_survive_post_receipt_candidate_or_binding_mutation(self):
        self.seed_partial(receipt=True)
        saved=self.revision.source_analyses.get(source_id__startswith='mapping:')
        payload=deepcopy(saved.payload)
        payload['photo_matches'][0]['candidates']=[{'field_id':'forged','reason':'ATTACK'}]
        # Isolated SQL mutation models the same out-of-band cache corruption in the original review.
        from core.survey_processing import digest
        with self.assertRaises(ValidationError):
            SurveySourceAnalysis.objects.filter(pk=saved.pk).update(payload=payload,digest=digest(payload))
        analyses=[r.payload for r in self.revision.source_analyses.exclude(source_id__startswith='mapping:')]
        job=self.revision.processing_job
        context=mapping.partial_mapping_context(analyses,self.revision.snapshot['schema'],job.model,job.model_digest)
        self.assertFalse(mapping.verified_partial_mapping(saved.source_id,payload,context))
    def test_partial_get_never_calls_mapping_or_retrieval(self):
        self.seed_partial(receipt=True)
        with patch.object(mapping,'bind_batch',side_effect=AssertionError('GET inference')), patch.object(mapping,'mapping_batches',side_effect=AssertionError('GET retrieval')):
            response=self.qa_state()
        self.assertTrue(response['photos'])
    def test_model_pin_change_withholds_previous_receipt(self):
        self.seed_partial(receipt=True)
        job=self.revision.processing_job
        job.model_digest='c'*64;job.save(update_fields=['model_digest'])
        self.assert_advice_withheld()

@override_settings(SECRET_KEY='independent-pr21-appsec',ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CacheAdversarialTests(documents.DocumentRepairTests):
    def cache(self):
        import pymupdf
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((72,72),'INDEPENDENT synthetic source')
            raw=pdf.tobytes()
        row=self.uploaded(kind='report',name='independent.pdf',raw=raw)
        url=reverse('photo_capture_document',args=[self.checklist.pk,row['id']])+'?preview=1&raster=1&page=1'
        image=self.read(self.client.get(url))
        folder=Path(settings.MEDIA_ROOT)/'survey_processing/document_previews'/str(row['id'])
        return url,image,folder,raw,row
    def test_signed_manifest_path_is_ignored_and_invalid_image_never_served(self):
        from core import engineer_documents as docs
        url,image,folder,raw,row=self.cache()
        manifest=next(folder.glob('*.json'))
        receipt=signing.loads(manifest.read_text(),salt=docs.PREVIEW_CACHE_SALT)
        evil=folder/'outside.png';evil.write_bytes(b'ATTACK')
        receipt['path']=str(evil)
        manifest.write_text(signing.dumps(receipt,salt=docs.PREVIEW_CACHE_SALT))
        self.assertEqual(self.read(self.client.get(url)),image)
        next(folder.glob('*-*.png')).write_bytes(b'CORRUPT PNG')
        self.assertEqual(self.read(self.client.get(url)),image)
        self.assertEqual(Path(SurveyDocument.objects.get(pk=row['id']).original.path).read_bytes(),raw)
    def test_verified_bytes_survive_cache_replacement_after_read(self):
        from core import engineer_documents as docs
        url,image,folder,raw,row=self.cache()
        opener=docs.default_storage.open
        class ReplacingStream:
            def __init__(self,stream,path):self.stream=stream;self.path=path
            def __enter__(self):return self
            def read(self,*args):
                value=self.stream.read(*args)
                Path(self.path).write_bytes(b'RACED')
                return value
            def __exit__(self,*args):self.stream.close()
        def raced(name,*args,**kwargs):
            stream=opener(name,*args,**kwargs)
            return ReplacingStream(stream,docs.default_storage.path(name)) if name.endswith('.png') else stream
        with patch.object(docs.default_storage,'open',side_effect=raced):
            self.assertEqual(self.read(self.client.get(url)),image)
    def test_foreign_engineer_and_client_denied_both_routes_and_revision_guesses(self):
        url,image,folder,raw,row=self.cache()
        self.upload('Civil');submitted,_=self.submit();self.assertEqual(submitted.status_code,201)
        revision=self.checklist.processing_revisions.get()
        foreign=self.person('independent_foreign','ENGINEER')
        for actor in [foreign,self.customer]:
            self.client.force_login(actor)
            for route in ['photo_capture_document','survey_processing_document']:
                for params in [{},{'revision_id':revision.pk},{'preview':1,'raster':1,'revision_id':revision.pk}]:
                    response=self.client.get(reverse(route,args=[self.checklist.pk,row['id']]),params)
                    self.assertIn(response.status_code,[403,404]);response.close()

class ObservationAdversarialTests(SimpleTestCase):
    def test_generated_advice_whitespace_and_empty_values_never_support_link(self):
        for value in [None,'',' \t\r\n ',[],{}]:
            self.assertFalse(mapping.has_source_observation({'value':value,'mapping_reason':'confident generated explanation'}))
        for value in [0,False]:
            self.assertTrue(mapping.has_source_observation({'value':value}))

# Avoid repeating inherited tests while retaining fixture helpers.
for cls,base in [(ControlAdversarialTests,controls.PauseCommandGenerationTests),(MappingAdversarialTests,matching.PartialMappingContextTests),(CacheAdversarialTests,documents.DocumentRepairTests)]:
    for name in dir(base):
        if name.startswith('test_') and name not in cls.__dict__:setattr(cls,name,None)

del cls,base

@override_settings(SECRET_KEY='independent-pr21-appsec',ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProgressAdversarialTests(progress_fixture.ProgressRevisionRepairTests):
    def test_same_task_unsubmitted_source_with_saved_analysis_is_still_denied(self):
        from core.qa_review_progress import progress
        from core.survey_processing import digest
        from django.http import Http404
        before=deepcopy(self.revision.snapshot)
        outside=self.add_photo('violet')
        payload={'findings':[{'value':'PRIVATE OUTSIDE REVISION'}]}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:'+str(outside.pk),payload=payload,digest=digest(payload))
        with self.assertRaises(Http404):
            progress(SimpleNamespace(user=self.quality,GET={'photo_id':str(outside.pk)}),self.checklist.pk)
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,before)
    def test_task_id_guess_and_foreign_reviewer_are_denied(self):
        from core.qa_review_progress import progress
        from django.http import Http404
        foreign=self.person('foreign_reviewer_probe','QUALITY_ENGINEER')
        for actor,ident in [(foreign,self.checklist.pk),(self.quality,999999999)]:
            with self.assertRaises(Http404):
                progress(SimpleNamespace(user=actor,GET={'photo_id':str(self.ids[0])}),ident)
ProgressAdversarialTests.test_same_task_photo_outside_frozen_revision_is_denied=None

@override_settings(SECRET_KEY='independent-pr21-appsec',ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RemovalAdversarialTests(CacheAdversarialTests):
    def test_missing_and_foreign_removal_never_change_source_or_membership(self):
        row=self.uploaded()
        doc=SurveyDocument.objects.get(pk=row['id'])
        before=Path(doc.original.path).read_bytes()
        self.checklist.refresh_from_db();metadata=deepcopy(self.checklist.intake_metadata)
        missing=self.client.post(reverse('photo_capture_document_remove',args=[999999999]),{'document_id':row['id']},content_type='application/json')
        self.assertEqual(missing.status_code,404)
        self.client.force_login(self.person('foreign_remove_probe','ENGINEER'))
        foreign=self.client.post(reverse('photo_capture_document_remove',args=[self.checklist.pk]),{'document_id':row['id']},content_type='application/json')
        self.assertEqual(foreign.status_code,404)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.intake_metadata,metadata)
        self.assertEqual(Path(doc.original.path).read_bytes(),before)
for _name in dir(CacheAdversarialTests):
    if _name.startswith('test_') and _name not in RemovalAdversarialTests.__dict__:setattr(RemovalAdversarialTests,_name,None)
del _name

from core import test_worker_runtime_tools as runtime_fixture
class RuntimeAdversarialTests(runtime_fixture.WorkerRuntimeToolTests):
    def test_loopback_url_obfuscations_cannot_select_foreign_or_credentialled_origins(self):
        for url in ['http://127.0.0.1.evil.invalid:11434','http://127.0.0.1@evil.invalid','http://evil.invalid@127.0.0.1','http://2130706433:11434','http://0177.0.0.1:11434','http://[::ffff:127.0.0.1]:11434','http://127.0.0.1:11434/../api','http://127.0.0.1:11434?secret=x','http://127.0.0.1:0','http://127.0.0.1:65536']:
            with self.subTest(url=url),self.assertRaises(ValueError):self.tools.loopback_origin(url)
        self.assertEqual(self.calls,[])
    def test_metadata_ignores_proxy_environment_and_never_requests_inference(self):
        import os
        with patch.dict(os.environ,{'HTTP_PROXY':'http://example.invalid:9999','http_proxy':'http://example.invalid:9999','NO_PROXY':'','no_proxy':''}):
            result=self.startup()
        self.assertTrue(result['worker_config_valid'])
        self.assertEqual([call[1] for call in self.calls],['/api/tags','/api/show'])
        self.assertNotIn(self.secret,str(result))
    def test_diagnostic_directory_symlink_is_rejected_without_touching_target(self):
        import tempfile
        local=self.directory/'.local';local.mkdir()
        with tempfile.TemporaryDirectory(prefix='pr21-outside-') as outside:
            (local/'diagnostics').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):
                self.tools.collect_diagnostics(project_root=self.directory,model=runtime_fixture.MODEL,photo_url=self.url,text_url=self.url)
            self.assertEqual(list(Path(outside).iterdir()),[])
for _name in dir(runtime_fixture.WorkerRuntimeToolTests):
    if _name.startswith('test_') and _name not in RuntimeAdversarialTests.__dict__:setattr(RuntimeAdversarialTests,_name,None)
del _name
