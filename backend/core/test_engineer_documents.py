"""Isolated sketch/report intake, immutable signatures and QA source access."""
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.db import DatabaseError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from . import category_intake, independent_workflow
from . import test_engineer_category_submission_acceptance as fixture
from .survey_processing_models import SurveyDocument, SurveyProcessingEvent, SurveyProcessingResult, SurveySourceAnalysis
from . import survey_processing as pipeline
from .models import Company, Project, Profile
from types import SimpleNamespace


@override_settings(SECRET_KEY='isolated-engineer-document-tests',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerDocumentTests(TestCase):
    setUp=fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person=fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=fixture.EngineerCategorySubmissionAcceptanceTests.post
    raw=fixture.EngineerCategorySubmissionAcceptanceTests.raw
    state=fixture.EngineerCategorySubmissionAcceptanceTests.state
    upload=fixture.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixture.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=fixture.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action=fixture.EngineerCategorySubmissionAcceptanceTests.qa_action
    route=fixture.EngineerCategorySubmissionAcceptanceTests.route

    def doc_upload(self, *,kind='hand_sketch',name='synthetic-sketch.png',raw=None,digest=None,files=None,finish=True):
        state=self.state()
        session=self.post('photo_processing_upload_session',{'action':'start'})
        self.assertEqual(session.status_code,200,session.content)
        token=session.json()['token']
        response=self.client.post(reverse('photo_capture_document_upload',args=[self.checklist.pk]),{
            'kind':kind,'expected_digest':digest or state['digest'],'processing_upload_token':token,
            'files':files if files is not None else [SimpleUploadedFile(name,raw if raw is not None else self.raw('sketch'))]})
        if finish:
            result=self.post('photo_processing_upload_session',{'action':'finish','token':token})
            self.assertEqual(result.status_code,200,result.content)
        return response

    def uploaded(self,**kwargs):
        response=self.doc_upload(**kwargs)
        self.assertEqual(response.status_code,201,response.content)
        return response.json()['documents'][0]

    def test_saved_contract_preserves_exact_originals_and_refresh(self):
        before=self.state()
        self.assertEqual(before['documents'],[])
        self.assertEqual(before['document_upload']['max_batch'],5)
        row=self.uploaded()
        refreshed=self.state()
        self.assertEqual(refreshed['documents'][0]['id'],row['id'])
        self.assertEqual(refreshed['documents'][0]['kind'],'hand_sketch')
        self.assertNotEqual(before['digest'],refreshed['digest'])
        document=SurveyDocument.objects.get(pk=row['id'])
        self.assertEqual(Path(document.original.path).read_bytes(),self.raw('sketch'))
        self.assertEqual(document.sha256,hashlib.sha256(self.raw('sketch')).hexdigest())
        self.assertEqual(refreshed['photos'],before['photos'],'Sketches must not become category photos')
        self.assertNotIn('analysis',refreshed['documents'][0])

    def test_duplicate_retries_and_soft_removal_restore_one_source(self):
        row=self.uploaded()
        repeated=self.uploaded()
        self.assertEqual(row['id'],repeated['id']);self.assertTrue(repeated['duplicate'])
        digest=self.state()['digest']
        removed=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':digest})
        self.assertEqual(removed.status_code,200,removed.content)
        self.assertEqual(removed.json()['documents'],[])
        again=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':digest})
        self.assertEqual(again.status_code,200,again.content)
        doc=SurveyDocument.objects.get(pk=row['id']);self.assertTrue(Path(doc.original.path).exists())
        restored=self.uploaded()
        self.assertTrue(restored['restored']);self.assertEqual(restored['id'],row['id'])
        self.assertEqual(SurveyDocument.objects.count(),1)

    def test_stale_changes_invalid_files_and_invalid_classification_do_not_save(self):
        digest=self.state()['digest'];row=self.uploaded()
        for args in [{'digest':digest},{'kind':'photo'},{'name':'not-supported.docx','raw':b'not a workbook'},
                     {'name':'broken.png','raw':b'broken image'}, {'files':[]}]:
            with self.subTest(args=list(args)):
                response=self.doc_upload(**args)
                self.assertIn(response.status_code,(400,409),response.content)
        stale=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':digest})
        self.assertEqual(stale.status_code,409,stale.content)
        self.assertEqual(SurveyDocument.objects.count(),1)
        self.assertEqual(len(self.state()['documents']),1)

    def test_batch_and_document_limits_are_enforced_before_storage(self):
        files=[SimpleUploadedFile(f'sketch-{index}.png',self.raw(str(index))) for index in range(6)]
        response=self.doc_upload(files=files)
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(SurveyDocument.objects.count(),0)
        with patch('core.engineer_documents.MAX_DOCUMENTS',0):
            response=self.doc_upload()
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(SurveyDocument.objects.count(),0)

    def test_unsupported_or_reassigned_roles_cannot_upload_remove_or_fetch_documents(self):
        row=self.uploaded();url=reverse('photo_capture_document',args=[self.checklist.pk,row['id']])
        for actor in [self.quality,self.lead,self.admin,self.customer]:
            self.client.force_login(actor)
            response=self.client.post(reverse('photo_capture_document_remove',args=[self.checklist.pk]),
                {'document_id':row['id'],'expected_digest':self.state()['digest']} if actor!=self.customer else {},
                content_type='application/json')
            self.assertIn(response.status_code,(403,404),response.content)
        self.client.force_login(self.engineer)
        foreign=self.person('foreign_doc_engineer',self.engineer.profile.role)
        self.client.force_login(foreign)
        self.assertEqual(self.client.get(url).status_code,404)
        self.client.logout();self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.customer);self.assertIn(self.client.get(url).status_code,(403,404))

    def test_documents_are_bound_to_processing_and_human_snapshots_without_changing_legacy_shape(self):
        self.checklist.refresh_from_db()
        self.assertNotIn('documents',independent_workflow.content_snapshot(self.checklist))
        row=self.uploaded();self.upload('Civil')
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        revision=self.checklist.processing_revisions.get();self.checklist.refresh_from_db()
        self.assertEqual(revision.snapshot['documents'][0]['id'],row['id'])
        self.assertEqual(revision.snapshot['documents'][0]['kind'],'hand_sketch')
        human=self.checklist.submission_revisions.get()
        self.assertEqual(human.snapshot['documents'][0]['id'],row['id'])
        self.assertTrue(pipeline.current(revision))
        self.assertFalse(self.state()['can_edit'])
        removed=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':self.state()['digest']})
        self.assertEqual(removed.status_code,403)
        self.assertEqual(revision.processing_job.status,'queued')

    def test_saved_documents_are_visible_to_qa_before_ai_with_frozen_revision_links(self):
        row=self.uploaded();self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        state=self.qa_state();document=state['documents'][0]
        self.assertEqual(document['id'],row['id']);self.assertIn('revision_id=',document['original_url'])
        self.assertEqual(state['ai']['status'],'queued')
        response=self.client.get(document['original_url'])
        self.assertEqual(response.status_code,200);self.assertEqual(b''.join(response.streaming_content),self.raw('sketch'))
        response=self.client.get(document['preview_url']);self.assertEqual(response.status_code,200)
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        response.close()

    def test_rejected_revision_documents_remain_downloadable_after_soft_removal(self):
        row=self.uploaded();self.upload('Civil');self.submit()
        original=self.qa_state()['documents'][0]['original_url']
        response=self.route(self.quality,'reject','Synthetic sketch needs correction')
        self.assertEqual(response.status_code,302,response.content)
        self.client.force_login(self.engineer)
        removed=self.post('photo_capture_document_remove',{'document_id':row['id'],'expected_digest':self.state()['digest']})
        self.assertEqual(removed.status_code,200,removed.content)
        self.assertEqual(self.client.get(reverse('photo_capture_document',args=[self.checklist.pk,row['id']])).status_code,404)
        self.assertEqual(self.client.get(reverse('survey_processing_document',args=[self.checklist.pk,row['id']])).status_code,404)
        historical=self.client.get(original);self.assertEqual(historical.status_code,200)
        self.assertEqual(b''.join(historical.streaming_content),self.raw('sketch'))
        historical.close()
        self.submit()
        self.assertEqual(self.checklist.processing_revisions.count(),2)
        self.assertEqual(self.qa_state()['documents'],[])

    def test_pdf_workbook_and_sketch_feed_existing_source_extraction(self):
        import pymupdf
        document=pymupdf.open();page=document.new_page();page.insert_text((72,72),'SYNTHETIC measured length 2 m')
        pdf=document.tobytes();document.close()
        buffer=BytesIO();book=Workbook();book.active.append(['Measurement','2 m']);book.save(buffer);book.close()
        self.uploaded(kind='report',name='synthetic-report.pdf',raw=pdf)
        self.uploaded(kind='report',name='synthetic-report.xlsx',raw=buffer.getvalue())
        self.uploaded()
        from .survey_evidence import extract_sources
        self.checklist.refresh_from_db();snapshot=category_intake.source_snapshot(self.checklist)
        records=[{**record,'path':SurveyDocument.objects.get(pk=record['id']).original.path} for record in snapshot['documents']]
        sources=list(extract_sources([],records))
        self.assertEqual(len(sources),3)
        self.assertTrue(any(source['image_b64'] for source in sources))
        self.assertTrue(any('2 m' in source['text'] for source in sources))

    def test_qa_acceptance_preserves_document_provenance_without_auto_approving_work(self):
        row=self.uploaded();self.upload('Civil');self.submit()
        revision=self.checklist.processing_revisions.get()
        source={'source_id':f'document:{row["id"]}','reference':'original'}
        finding={**source,'field_hint':'manufacturer','value':'SyntheticCo','confidence':'high'}
        package=pipeline.prepare_checklist(revision.snapshot,{'findings':[finding],'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=revision,payload=package,digest=pipeline.digest(package))
        before=self.qa_state();item=next(item for item in before['items'] if item['id']=='manufacturer')
        self.assertFalse(item['accepted']);self.assertEqual(item['sources'],[source])
        response=self.qa_action('answer',field_id='manufacturer',value='SyntheticCo',photo_ids=[],reason='Read submitted report label')
        self.assertEqual(response.status_code,200,response.content)
        item=next(item for item in response.json()['items'] if item['id']=='manufacturer')
        self.assertEqual(item['sources'],[source]);self.assertTrue(item['accepted'])
        self.assertEqual(item['status'],'Confirmed from evidence')
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.review_route_record.stage,'quality_engineer')

    def test_save_failure_rolls_back_rows_and_new_files(self):
        before=self.state()['digest']
        with patch('core.engineer_documents.SurveyDocument.save',side_effect=DatabaseError('isolated save failure')):
            response=self.doc_upload()
        self.assertEqual(response.status_code,503,response.content)
        self.assertEqual(SurveyDocument.objects.count(),0)
        self.assertEqual(self.state()['digest'],before)
        self.assertFalse([path for path in (Path(settings.MEDIA_ROOT)/'survey_processing/documents').rglob('*') if path.is_file()])

    def test_shared_document_upload_session_blocks_submit_until_finished(self):
        self.upload('Civil')
        result=self.doc_upload(finish=False)
        self.assertEqual(result.status_code,201,result.content)
        response,_=self.submit()
        self.assertEqual(response.status_code,409,response.content)
        self.assertIn('Uploads are still open',response.json()['error'])
        token=self.state()['upload_state']['own_tokens'][0]
        response=self.post('photo_processing_upload_session',{'action':'finish','token':token})
        self.assertEqual(response.status_code,200,response.content)
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(len(self.qa_state()['documents']),1)

    def test_document_file_cross_project_access_revocation_and_csrf_are_denied(self):
        row=self.uploaded()
        url=reverse('photo_capture_document',args=[self.checklist.pk,row['id']])
        company=Company.objects.create(name='Synthetic document foreign company')
        project=Project.objects.create(name='Synthetic document foreign project',company=company)
        foreign=self.person('foreign_document_quality',Profile.Roles.QUALITY_ENGINEER,project)
        self.client.force_login(foreign)
        self.assertEqual(self.client.get(url).status_code,404)
        self.engineer.is_active=False;self.engineer.save(update_fields=['is_active'])
        self.client.force_login(self.engineer)
        self.assertIn(self.client.get(url).status_code,(302,403,404))
        self.engineer.is_active=True;self.engineer.save(update_fields=['is_active'])
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.engineer)
        response=strict.post(reverse('photo_capture_document_remove',args=[self.checklist.pk]),
            {'document_id':row['id'],'expected_digest':'stale'},content_type='application/json')
        self.assertEqual(response.status_code,403)
        self.assertEqual(SurveyDocument.objects.count(),1)

    def test_only_qa_receives_saved_document_analysis_for_its_submitted_revision(self):
        row=self.uploaded();self.upload('Civil');self.submit()
        revision=self.checklist.processing_revisions.get()
        payload={'reference':'original','findings':[{'value':'SYNTHETIC site note','field_hint':'contact'}],
            'missing':['No calibrated dimension'],'conflicts':[]}
        SurveySourceAnalysis.objects.create(revision=revision,source_id=f'document:{row["id"]}',
            payload=payload,digest=pipeline.digest(payload))
        state=self.qa_state()
        self.assertEqual(state['documents'][0]['analyses'][0]['findings'],payload['findings'])
        self.assertEqual(state['documents'][0]['analyses'][0]['missing'],payload['missing'])
        lead=self.qa_state(self.lead)
        self.assertNotIn('analyses',lead['documents'][0])
        self.client.force_login(self.engineer)
        self.assertNotIn('analyses',self.state()['documents'][0])

    def test_photo_required_field_is_not_satisfied_by_a_report_link_alone(self):
        row=self.uploaded();self.upload('Civil');self.submit()
        revision=self.checklist.processing_revisions.get()
        self.checklist.refresh_from_db()
        self.checklist.schema_snapshot['sections'][0]['fields'][2]['photo_required']=True
        # Unit-level rule evaluation uses a consistent in-memory approved
        # definition. No submitted/published row is changed for this case.
        self.checklist.checklist_template.definition=deepcopy(self.checklist.schema_snapshot)
        package=pipeline.prepare_checklist(revision.snapshot,{'findings':[],'missing':[],'conflicts':[]})
        item=next(item for item in package['checklist_items'] if item['id']=='manufacturer')
        item.update(value='SyntheticCo',accepted=True,sources=[{'source_id':f'document:{row["id"]}','reference':'original'}])
        with patch('core.category_intake.reviewed_payload',return_value=package):
            missing=category_intake.missing_for_review(self.checklist)
        self.assertTrue(any('Cabinet manufacturer requires matched source evidence' in message for message in missing),missing)


class EngineerDocumentUnitTests(SimpleTestCase):
    def test_legacy_snapshot_shape_is_unchanged_without_versioned_opt_in(self):
        from .engineer_documents import snapshot
        records=[{'id':1,'filename':'old.pdf'}]
        self.assertEqual(snapshot(SimpleNamespace(intake_metadata={}),records),records)
        self.assertEqual(snapshot(SimpleNamespace(intake_metadata={'capture_documents':{'version':999}}),records),records)

    def test_document_exclusions_and_kinds_do_not_modify_source_records(self):
        from .engineer_documents import snapshot
        records=[{'id':1,'filename':'sketch.png'},{'id':2,'filename':'report.pdf'}]
        before=deepcopy(records)
        c=SimpleNamespace(intake_metadata={'capture_documents':{'version':1,'kinds':{'1':'hand_sketch'},'excluded':[2]}})
        self.assertEqual(snapshot(c,records),[{'id':1,'filename':'sketch.png','kind':'hand_sketch'}])
        self.assertEqual(records,before)

    def test_photo_only_edits_retain_only_existing_revision_document_sources(self):
        from .engineer_documents import retained_item_sources
        valid={'source_id':'document:3:page:2','reference':'page 2'}
        payload={'checklist_items':[{'id':'x','sources':[valid,valid,
            {'source_id':'document:4','reference':'foreign'}, {'source_id':'photo:3','reference':'photo'}]}]}
        revision=SimpleNamespace(snapshot={'documents':[{'id':3}]})
        result=retained_item_sources(revision,payload,'x')
        self.assertEqual(result,[valid]);result[0]['reference']='edited'
        self.assertEqual(valid['reference'],'page 2')

