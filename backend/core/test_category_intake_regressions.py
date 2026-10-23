"""Additional category-intake edges against real isolated Django endpoints."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from . import category_intake
from . import test_engineer_category_submission_acceptance as capture_fixtures


@override_settings(SECRET_KEY='isolated-category-edge-regressions', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CategoryIntakeRegressionTests(TestCase):
    # Reuse fixture construction, never inherit and rerun its independent cases.
    setUp = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.setUp
    person = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted
    qa_state = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_action
    route = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually = capture_fixtures.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def test_explicit_reupload_restores_excluded_original_without_changing_category(self):
        original, _ = self.upload('Civil')
        photo = self.checklist.photo_evidence.get(pk=original[0]['id'])
        raw = Path(photo.original.path).read_bytes()
        removed = self.post('photo_capture_remove', {'photo_id': photo.pk,
            'expected_digest': self.state()['digest']})
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertEqual(self.state()['photos'], [])
        restored, _ = self.upload('Tower')
        self.assertEqual(restored[0]['id'], photo.pk)
        self.assertEqual(self.checklist.photo_evidence.count(), 1)
        self.assertEqual(self.state()['photos'][0]['group'], 'Civil')
        self.assertEqual(Path(photo.original.path).read_bytes(), raw)

    def test_team_lead_return_reopens_only_qa_overlay_and_retains_source_snapshot(self):
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.assert_submitted()
        frozen = deepcopy(revision.snapshot)
        self.complete_qa_manually()
        self.assertEqual(self.route(self.quality, 'approve').status_code, 302)
        self.assertEqual(self.route(self.lead, 'reject', 'Clarify the recorded contact').status_code, 302)
        self.assertFalse(self.qa_state()['completed'])
        page=self.client.get(reverse('custom_checklist',args=[self.checklist.pk]))
        self.assertEqual(page.status_code,200)
        self.assertTrue(page.context['review_route']['qa_review_required'])
        self.assertFalse(page.context['review_route']['can_clarify'])
        self.assertContains(page,'Review and complete QA evidence')
        self.assertNotContains(page,'name="action" value="clarify"')
        correction = self.qa_action('answer', field_id='contact', value='Corrected source contact',
            photo_ids=[], reason='Checked the submitted source with the surveyor')
        self.assertEqual(correction.status_code, 200, correction.content)
        self.assertEqual(self.qa_action('complete').status_code, 200)
        page=self.client.get(reverse('custom_checklist',args=[self.checklist.pk]))
        self.assertTrue(page.context['review_route']['can_clarify'])
        self.assertContains(page,'name="action" value="clarify"')
        self.assertEqual(self.route(self.quality, 'clarify', 'Source contact corrected').status_code, 302)
        self.assertEqual(self.route(self.lead, 'approve').status_code, 302)
        revision.refresh_from_db(); self.checklist.refresh_from_db()
        self.assertEqual(revision.snapshot, frozen)
        self.assertEqual(self.checklist.answer_data, frozen['answers'])
        self.assertEqual(revision.processing_events.filter(action='qa_reopen').count(), 1)

    def test_returned_engineer_still_cannot_use_legacy_ai_mutations(self):
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.assert_submitted()
        self.assertEqual(self.route(self.quality, 'reject', 'Add missing source photo').status_code, 302)
        self.client.force_login(self.engineer)
        self.assertEqual(self.state()['correction_reason'],'Add missing source photo')
        for decision in ['accept', 'engineer_complete', 'correct']:
            denied = self.client.post(reverse('survey_processing_action', args=[self.checklist.pk]),
                {'action': 'review', 'revision_id': revision.pk, 'decision': decision,
                 'finding_ids': '["manufacturer"]', 'reason': 'Engineer is not a QA reviewer'})
            self.assertEqual(denied.status_code, 403, denied.content)
        self.assertFalse(revision.processing_events.filter(action='engineer_complete').exists())

    def test_nonfinite_number_is_rejected_without_saving_a_qa_event(self):
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.assert_submitted()
        before = revision.processing_events.count()
        for value in ['NaN', 'Infinity', '-Infinity', 'not a number']:
            result = self.qa_action('answer', field_id='tower_height', value=value,
                photo_ids=[], reason='Invalid numeric source must not save')
            self.assertEqual(result.status_code, 409, result.content)
        self.assertEqual(revision.processing_events.count(), before)

    def test_completed_qa_package_locks_mutations_without_routing_approval(self):
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201, response.content)
        revision = self.assert_submitted()
        self.complete_qa_manually()
        package = deepcopy(category_intake.reviewed_payload(revision))
        denied = self.qa_action('answer', field_id='contact', value='Silent overwrite',
            photo_ids=[], reason='Must return through the review route first')
        self.assertEqual(denied.status_code, 409, denied.content)
        self.assertEqual(category_intake.reviewed_payload(revision), package)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
        self.assertFalse(revision.processing_events.filter(action='technical_approve').exists())

    def test_qa_accepted_answer_with_no_sources_clears_only_current_legacy_photo_projection(self):
        self.upload('Civil')
        photo=self.checklist.photo_evidence.get()
        original=Path(photo.original.path).read_bytes()
        self.checklist.image_data={'contact':[photo.original.name],'tower_height':[photo.original.name]}
        self.checklist.answer_data={'custom':{'tower_height':'23'}}
        self.checklist.save(update_fields=['image_data','answer_data'])
        response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        revision=self.assert_submitted()
        frozen=deepcopy(revision.snapshot)
        self.complete_qa_manually()
        self.checklist.refresh_from_db()
        view=category_intake.projected_checklist(self.checklist)
        self.assertEqual(view.image_data.get('contact',[]),[])
        self.assertEqual(view.image_data.get('tower_height',[]),[])
        self.assertNotIn('tower_height',view.answer_data['custom'])
        self.assertEqual(self.checklist.answer_data['custom']['tower_height'],'23')
        self.assertEqual(self.checklist.image_data['contact'],[photo.original.name])
        missing=self.client.get(reverse('custom_checklist_photo',args=[self.checklist.pk,'contact',0]))
        self.assertEqual(missing.status_code,404)
        from openpyxl import load_workbook
        report=self.client.get(reverse('custom_checklist_download',args=[self.checklist.pk]))
        self.assertEqual(report.status_code,200,report.content[:200])
        workbook=load_workbook(BytesIO(report.content))
        self.assertEqual(len(workbook['Site survey']._images),1)
        workbook.close()
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot,frozen)
        self.assertEqual(Path(photo.original.path).read_bytes(),original)

    def test_legacy_governance_category_submission_freezes_source_against_admin_and_lead_aliases(self):
        from .models import Checklist,ChecklistTemplate,PhotoPlacement
        self.project.review_layers=None;self.project.save(update_fields=['review_layers'])
        excluded=ChecklistTemplate.objects.create(name='Synthetic legacy category scope',published=True,
            definition=deepcopy(self.schema),checklist_required=False)
        self.checklist=Checklist.objects.create(project=self.project,user=self.engineer,
            quality_reviewer=self.quality,checklist_template=excluded,site_id='SYNTHETIC-LEGACY-CATEGORY',
            governance_mode=Checklist.GovernanceMode.LEGACY)
        self.upload('Civil')
        submitted,_=self.submit()
        self.assertEqual(submitted.status_code,201,submitted.content)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.governance_mode,Checklist.GovernanceMode.LEGACY)
        revision=self.checklist.processing_revisions.get()
        frozen=deepcopy(revision.snapshot)
        photo=self.checklist.photo_evidence.get()
        original=Path(photo.original.path).read_bytes()
        for actor in [self.admin,self.lead]:
            self.client.force_login(actor)
            page=self.client.get(reverse('custom_checklist',args=[self.checklist.pk]))
            self.assertEqual(page.status_code,200,page.content)
            self.assertFalse(page.context['can_edit'])
            for route,data in [('custom_checklist_save',{'answers':{'manufacturer':'Forbidden overwrite'}}),
                ('photo_mapping',{'decisions':[{'photo_id':photo.pk,'field_id':'manufacturer','action':'manual'}]}),
                ('photo_enqueue',{'photo_ids':[photo.pk]})]:
                result=self.post(route,data,actor=actor)
                self.assertEqual(result.status_code,403,result.content)
            self.client.force_login(actor)
            upload=self.client.post(reverse('photo_upload',args=[self.checklist.pk]),
                {'group':'Civil','files':[SimpleUploadedFile('forbidden-extra.png',self.raw('forbidden-extra'),content_type='image/png')]})
            self.assertEqual(upload.status_code,403,upload.content)
        self.checklist.refresh_from_db();revision.refresh_from_db()
        self.assertEqual(self.checklist.answer_data,frozen['answers'])
        self.assertEqual(self.checklist.photo_evidence.count(),1)
        self.assertFalse(PhotoPlacement.objects.filter(photo__checklist=self.checklist).exists())
        self.assertEqual(revision.snapshot,frozen)
        self.assertEqual(Path(photo.original.path).read_bytes(),original)
