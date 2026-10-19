"""Immutable canonical evidence and peer-reviewed, exact-source learning contracts."""
import json
from copy import deepcopy
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from .models import Company, Project, Profile, ChecklistTemplate, Checklist, PhotoEvidence
from .evidence_models import EvidenceAnalysisRecord, EvidenceCorrection, EvidenceCorrectionDecision, EvidenceRuleRelease
from .evidence_learning import (analysis_key, find_analysis, get_or_create_analysis, capture_correction,
                                decide_correction, publish_release, release_references, learning_state)


@override_settings(SECRET_KEY='isolated-evidence-learning-tests', ROOT_URLCONF='core.evidence_urls',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EvidenceLearningTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Synthetic evidence tenant')
        self.template = ChecklistTemplate.objects.create(name='Synthetic evidence', published=True,
            definition={'sections': [{'id': 'general', 'title': 'General', 'fields': [
                {'id': 'base', 'label': 'Concrete tower foundation', 'type': 'photo'}]}]})
        self.project = Project.objects.create(name='Synthetic evidence project', company=self.company, checklist_template=self.template)
        self.engineer = self.person('engineer', Profile.Roles.ENGINEER)
        self.quality = self.person('quality', Profile.Roles.QUALITY_ENGINEER)
        self.lead = self.person('lead', Profile.Roles.TEAM_LEAD)
        self.client_user = self.person('customer', Profile.Roles.CLIENT)
        self.admin = self.person('admin', Profile.Roles.ADMIN)
        self.superuser = self.person('super', Profile.Roles.SUPER_ADMIN, superuser=True)
        self.other_quality = self.person('other_quality', Profile.Roles.QUALITY_ENGINEER)
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-EVIDENCE-01')
        self.photo = PhotoEvidence.objects.create(checklist=self.checklist, filename='synthetic.png', sha256='a' * 64,
            analysis_metadata={'caption': 'Concrete foundation beneath tower.'})
        self.versions = {'rules_version': 'rules-1', 'model_version': 'synthetic-model-hash',
                         'tool_version': 'tools-1', 'prompt_version': 'prompt-1', 'release_digest': 'none'}

    def person(self, name, role, superuser=False):
        user = User.objects.create_user('evidence_' + name, is_superuser=superuser)
        user.profile.role = role
        user.profile.company = self.company
        user.profile.project = self.project
        user.profile.save()
        return user

    def correction(self, action='reject', actor=None):
        return capture_correction(actor or self.engineer, self.checklist, self.photo, 'base', action,
                                  'Synthetic human reviewed source evidence')

    def pristine(self):
        self.checklist.refresh_from_db()
        return deepcopy((self.checklist.answer_data, self.checklist.section_approvals,
                         self.checklist.quality_approval, self.checklist.client_approval, self.checklist.review_history))

    def test_canonical_result_saved_once_and_reused_across_authorized_actors(self):
        before = self.pristine()
        record, reused = get_or_create_analysis(self.checklist, self.photo, {'z': 2, 'a': {'answer': None}}, self.versions)
        self.assertFalse(reused)
        for actor in [self.engineer, self.quality, self.lead]:
            learning_state(actor, self.checklist.pk)
            cached, reused = get_or_create_analysis(self.checklist, self.photo, {'different': 'later stochastic result'}, self.versions)
            self.assertTrue(reused)
            self.assertEqual(cached.pk, record.pk)
            self.assertEqual(cached.payload, {'a': {'answer': None}, 'z': 2})
        self.assertEqual(EvidenceAnalysisRecord.objects.count(), 1)
        self.assertEqual(before, self.pristine())

    def test_cache_invalidates_every_version_and_extra_input_fingerprint(self):
        original = analysis_key(self.checklist, self.photo, self.versions)
        for key in self.versions:
            changed = {**self.versions, key: self.versions[key] + '-changed'}
            self.assertNotEqual(original, analysis_key(self.checklist, self.photo, changed))
        original_record, _ = get_or_create_analysis(self.checklist, self.photo, {'result': []}, self.versions)
        self.photo.sha256 = 'b' * 64
        self.photo.save()
        self.assertIsNone(find_analysis(self.checklist, self.photo, self.versions))
        self.assertEqual(original_record.photo_sha256, 'a' * 64)
        self.checklist.schema_snapshot['sections'][0]['fields'][0]['label'] = 'Changed wording'
        self.assertNotEqual(original, analysis_key(self.checklist, self.photo, self.versions))

    def test_sitewide_review_without_photo_is_keyed_by_explicit_input_digest(self):
        versions = {**self.versions, 'input_digest': 'site-snapshot-1'}
        one, _ = get_or_create_analysis(self.checklist, None, {'findings': []}, versions)
        two, reused = get_or_create_analysis(self.checklist, None, {'findings': ['different']}, versions)
        self.assertTrue(reused)
        self.assertEqual(one.pk, two.pk)
        self.assertIsNone(one.photo_id)
        self.assertIsNone(find_analysis(self.checklist, None, {**versions, 'input_digest': 'site-snapshot-2'}))

    def test_nonfinite_or_unversioned_payload_never_persists(self):
        with self.assertRaises(ValidationError):
            get_or_create_analysis(self.checklist, self.photo, {'score': float('nan')}, self.versions)
        with self.assertRaises(ValidationError):
            get_or_create_analysis(self.checklist, self.photo, {}, {})
        self.assertEqual(EvidenceAnalysisRecord.objects.count(), 0)

    def test_rejected_learning_case_not_published_and_negative_reference_requires_peer_approval(self):
        before = self.pristine()
        case = self.correction()
        with self.assertRaises(PermissionDenied):
            decide_correction(self.engineer, self.checklist.pk, case.pk, 'approved', 'Self grant')
        with self.assertRaises(ValidationError):
            publish_release(self.lead, self.checklist.pk, [case.pk], 'Unreviewed')
        decide_correction(self.quality, self.checklist.pk, case.pk, 'rejected', 'Not trustworthy evidence')
        with self.assertRaises(ValidationError):
            publish_release(self.lead, self.checklist.pk, [case.pk], 'Rejected')
        accepted = self.correction()
        decide_correction(self.quality, self.checklist.pk, accepted.pk, 'approved', 'Confirmed incorrect pairing')
        release = publish_release(self.lead, self.checklist.pk, [accepted.pk], 'Explicit negative example release')
        reference = release_references(release)[0]
        self.assertEqual(reference['polarity'], 'negative')
        self.assertEqual(reference['photo_sha256'], self.photo.sha256)
        self.assertEqual(reference['project_id'], self.project.pk)
        self.assertEqual(reference['field_id'], 'base')
        self.assertEqual(before, self.pristine())

    def test_peer_cannot_review_own_case_and_decision_cannot_be_replaced(self):
        case = self.correction(actor=self.quality)
        with self.assertRaises(PermissionDenied):
            decide_correction(self.quality, self.checklist.pk, case.pk, 'approved', 'Own case')
        decision = decide_correction(self.lead, self.checklist.pk, case.pk, 'approved', 'Peer review')
        with self.assertRaises(ValidationError):
            decide_correction(self.lead, self.checklist.pk, case.pk, 'rejected', 'Replace signature')
        with self.assertRaises(ValidationError):
            EvidenceCorrectionDecision.objects.filter(pk=decision.pk).update(reason='Replaced')

    def test_release_is_additive_and_old_results_and_releases_stay_frozen(self):
        from .models import PhotoPlacement
        placement=PhotoPlacement.objects.create(photo=self.photo,field_id='base',section_id='general',status='confirmed',reason='Existing human confirmation')
        preserved=(placement.status,placement.reason,placement.reviewed_by_id)
        case = self.correction('manual')
        decide_correction(self.quality, self.checklist.pk, case.pk, 'approved', 'Peer verified')
        first = publish_release(self.lead, self.checklist.pk, [case.pk], 'First release')
        old_versions = {**self.versions, 'release_digest': first.digest}
        original, _ = get_or_create_analysis(self.checklist, self.photo, {'finding': 'original'}, old_versions)
        next_case = self.correction('reject')
        decide_correction(self.quality, self.checklist.pk, next_case.pk, 'approved', 'Second peer review')
        second = publish_release(self.lead, self.checklist.pk, [next_case.pk], 'Next release')
        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(len(first.references), 1)
        self.assertEqual(len(second.references), 2)
        self.assertEqual(find_analysis(self.checklist, self.photo, old_versions).pk, original.pk)
        self.assertIsNone(find_analysis(self.checklist, self.photo, {**self.versions, 'release_digest': second.digest}))
        for model, instance in [(EvidenceRuleRelease, first), (EvidenceCorrection, case), (EvidenceAnalysisRecord, original)]:
            with self.assertRaises(ValidationError):
                model.objects.filter(pk=instance.pk).delete()
            with self.assertRaises(ValidationError):
                instance.save()
        released = release_references(first)
        released[0]['polarity'] = 'changed externally'
        self.assertEqual(first.references[0]['polarity'], 'positive')
        placement.refresh_from_db()
        self.assertEqual((placement.status,placement.reason,placement.reviewed_by_id),preserved)

    def test_project_release_history_does_not_leak_another_engineers_source(self):
        case=self.correction('manual')
        decide_correction(self.quality,self.checklist.pk,case.pk,'approved','Peer inspected original')
        publish_release(self.lead,self.checklist.pk,[case.pk],'Project release')
        other=self.person('another_engineer',Profile.Roles.ENGINEER)
        own=Checklist.objects.create(project=self.project,user=other,quality_reviewer=self.quality,site_id='OTHER-SITE')
        state=learning_state(other,own.pk)
        self.assertEqual(state['current_release']['version'],1)
        self.assertEqual(state['current_release']['references'],[])
        self.assertEqual(state['cases'],[])

    def test_internal_scope_denies_super_client_admin_unassigned_quality_and_foreign_company(self):
        for actor in [self.superuser, self.client_user, self.admin, self.other_quality]:
            self.client.force_login(actor)
            response = self.client.get(reverse('evidence_learning_state', args=[self.checklist.pk]))
            self.assertIn(response.status_code, [403, 404])
        foreign = Company.objects.create(name='Different tenant')
        self.lead.profile.company = foreign
        self.lead.profile.save()
        self.client.force_login(self.lead)
        self.assertEqual(self.client.get(reverse('evidence_learning_state', args=[self.checklist.pk])).status_code, 404)

    def test_csrf_required_and_formdata_publish_receives_json_success(self):
        case = self.correction()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.quality)
        url = reverse('evidence_learning_decide', args=[self.checklist.pk, case.pk])
        self.assertEqual(csrf_client.post(url, {'decision': 'approved', 'reason': 'Missing CSRF'}).status_code, 403)
        self.client.force_login(self.quality)
        approved = self.client.post(url, {'decision': 'approved', 'reason': 'Explicit peer decision'}, HTTP_ACCEPT='application/json')
        self.assertEqual(approved.status_code, 200)
        response = self.client.post(reverse('evidence_learning_publish', args=[self.checklist.pk]),
            {'case_ids': [case.pk], 'reason': 'Explicit form release'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['current_release']['version'], 1)

    def test_release_cannot_import_another_project_case_or_unknown_source(self):
        other = Project.objects.create(name='Other project', company=self.company, checklist_template=self.template)
        foreign = Checklist.objects.create(user=self.engineer, project=other, site_id='FOREIGN')
        photo = PhotoEvidence.objects.create(checklist=foreign, filename='other.png', sha256='c' * 64)
        with self.assertRaises(ValidationError):
            capture_correction(self.engineer, self.checklist, photo, 'base', 'manual')
        with self.assertRaises(ValidationError):
            capture_correction(self.engineer, self.checklist, self.photo, 'unknown', 'manual')
        with self.assertRaises(ValidationError):
            publish_release(self.quality, self.checklist.pk, [999999], 'Unknown case')
