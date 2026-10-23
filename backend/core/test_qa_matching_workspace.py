"""Independent persistence/permission tests for the owner's QA matching workspace.

The browser checks cover physical DnD/touch and rollback presentation. Here real
Django HTTP requests and saved records verify links, revisions, ordering and
engineering-decision separation. AI observations are explicitly synthetic.
"""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from openpyxl import load_workbook

from . import survey_processing as pipeline, test_survey_processing as fixtures
from .independent_workflow import configure_policy
from .models import (Checklist, ChecklistTemplate, PhotoEvidence, Profile, WorkAssignment,
                     WorkflowTemplateQualification)
from .review_route_service import route_context
from .roadmap_service import definition_digest
from .survey_processing_models import (SurveyProcessingEvent, SurveyProcessingResult,
                                      SurveySourceAnalysis)


@override_settings(SECRET_KEY='isolated-qa-matching-workspace', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAMatchingWorkspaceTests(TestCase):
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo

    def setUp(self):
        fixtures.SurveyProcessingTests.setUp(self)
        self.schema = {'title': 'SYNTHETIC approved QA matching requirements', 'sections': [
            {'id': 'general', 'title': 'Recorded information', 'group': 'General Info', 'fields': [
                {'id': 'contact', 'label': 'Recorded contact', 'type': 'text', 'required': True}]},
            {'id': 'civil', 'title': 'Foundations', 'group': 'Civil', 'fields': [
                {'id': 'foundation', 'label': 'Foundation inspection', 'type': 'inspection'},
                {'id': 'civil_photo', 'label': 'Foundation source evidence', 'type': 'photo', 'required': True,
                 'evidence_rules': {'min_photos': 2}}]},
            {'id': 'electrical', 'title': 'Cabinet labels', 'group': 'electrical', 'fields': [
                {'id': 'manufacturer', 'label': 'Manufacturer', 'type': 'text',
                 'description': 'Read the visible manufacturer label; do not invent concealed equipment.'},
                {'id': 'model', 'label': 'Recorded model', 'type': 'text'}]},
            {'id': 'tower', 'title': 'Tower labels', 'group': 'Tower', 'fields': [
                {'id': 'antenna_label', 'label': 'Antenna label', 'type': 'text'},
                {'id': 'tower_height', 'label': 'Recorded tower height', 'type': 'number', 'unit': 'm'}]},
            {'id': 'special', 'title': 'Specialist note', 'group': 'Unclassified original heading', 'fields': [
                {'id': 'special_note', 'label': 'Specialist note', 'type': 'text'}]},
        ]}
        self.template = ChecklistTemplate.objects.create(name='SYNTHETIC QA matching template',
            definition=deepcopy(self.schema), published=True, checklist_required=True)
        self.project.checklist_template = self.template
        self.project.review_layers = 4
        self.project.save(update_fields=['checklist_template', 'review_layers'])
        self.checklist = Checklist.objects.create(project=self.project, user=self.engineer,
            quality_reviewer=self.quality, site_id='SYNTHETIC-QA-MATCHING', answer_data={},
            coordinate_reference={'source': 'Explicit synthetic recorded coordinates', 'crs': 'EPSG:4326'})
        WorkflowTemplateQualification.objects.create(project=self.project, template=self.template,
            workflow_type=self.checklist.workflow_type, definition_digest=definition_digest(self.schema),
            criteria_reference='SYNTHETIC recorded-label requirement', inspection_method='Inspect sources',
            reviewed_by=self.lead, reason='Isolated matching acceptance')
        configure_policy(self.admin, self.checklist, self.quality, self.lead,
            'Synthetic named reviewers', customer_reviewer=self.customer, customer_required=True, enable_route=True)
        self.assignment = WorkAssignment.objects.create(project=self.project, assigned_by=self.lead,
            assigned_to=self.engineer, checklist=self.checklist, site_id=self.checklist.site_id,
            latitude=24, longitude=46, description='SYNTHETIC QA matching only')
        self.photos = {}
        for category, color in [('', 'blue'), ('Civil', 'green'), ('Electrical', 'red'), ('Tower', 'yellow')]:
            image = BytesIO()
            Image.new('RGB', (70, 46), color).save(image, 'PNG')
            raw = image.getvalue()
            photo = PhotoEvidence(checklist=self.checklist, uploaded_by=self.engineer,
                filename='synthetic-' + (category or 'general') + '.png', group=category,
                sha256=hashlib.sha256(raw).hexdigest(), metadata={'format': 'PNG', 'width': 70, 'height': 46})
            from django.core.files.base import ContentFile
            photo.original.save('source.bin', ContentFile(raw), save=False)
            photo.preview.save('preview.png', ContentFile(raw), save=False)
            photo.save()
            self.photos[category] = photo
        self.client.force_login(self.engineer)
        self.submit_capture()
        self.revision = self.checklist.processing_revisions.get()
        self.client.force_login(self.quality)

    def submit_capture(self):
        state = self.client.get(reverse('photo_capture_state', args=[self.checklist.pk]))
        self.assertEqual(state.status_code, 200, state.content)
        response = self.client.post(reverse('photo_capture_submit', args=[self.checklist.pk]),
            json.dumps({'uploads_finished': True, 'expected_digest': state.json()['digest']}),
            content_type='application/json')
        self.assertIn(response.status_code, (200, 201), response.content)
        self.checklist.refresh_from_db()
        return response

    def state(self, actor=None):
        self.client.force_login(actor or self.quality)
        response = self.client.get(reverse('photo_capture_review_state', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def mutate(self, action, actor=None, state=None, **values):
        state = state or self.state(actor)
        self.client.force_login(actor or self.quality)
        payload = {'action': action, 'revision_id': state['revision_id'],
            'source_digest': state['source_digest'], 'reason': 'Synthetic QA source review', **values}
        if action == 'reorder':
            payload.setdefault('expected_order_digest', state['order_digest'])
        else:
            payload.setdefault('expected_review_digest', state['review_digest'])
        return self.client.post(reverse('photo_capture_review_action', args=[self.checklist.pk]),
            json.dumps(payload), content_type='application/json')

    def pairs(self, state):
        return {(link['photo_id'], link['field_id']) for link in state['links']}

    def confirm(self, photo, field):
        response = self.mutate('confirm_link', photo_id=photo.pk, field_id=field)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def route(self, actor, action):
        self.checklist.refresh_from_db()
        self.client.force_login(actor)
        context = route_context(actor, self.checklist)
        response = self.client.post(reverse('review_route_action', args=[self.checklist.pk]),
            {'action': action, 'reason': 'Synthetic authorized reviewer decision',
             'expected_token': context['token']})
        self.assertEqual(response.status_code, 302, response.content)
        self.checklist.refresh_from_db()

    def ai_result(self):
        electrical = self.photos['Electrical']
        general = self.photos['']
        raw = [
            {'field_hint': 'manufacturer', 'value': 'SyntheticCo', 'confidence': 'high',
             'source_id': 'photo:' + str(electrical.pk), 'reference': electrical.filename,
             'verification_status': 'needs_review', 'reason': 'Visible synthetic cabinet label'},
            {'field_hint': 'contact', 'value': None, 'confidence': 'high',
             'source_id': 'photo:' + str(general.pk), 'reference': general.filename,
             'verification_status': 'needs_review', 'reason': 'No readable contact recorded'},
            {'field_hint': 'NOT_AN_APPROVED_ID', 'value': 'Unsupported proposed point', 'confidence': 'high',
             'source_id': 'photo:' + str(general.pk), 'reference': general.filename,
             'verification_status': 'needs_review'},
        ]
        payload = pipeline.prepare_checklist(self.revision.snapshot,
            {'findings': raw, 'missing': [], 'conflicts': []})
        SurveyProcessingResult.objects.create(revision=self.revision, payload=payload, digest=pipeline.digest(payload))
        observation = {'source_id': 'photo:' + str(electrical.pk), 'reference': electrical.filename,
            'findings': [raw[0]], 'model': 'SYNTHETIC controlled result'}
        SurveySourceAnalysis.objects.create(revision=self.revision, source_id=observation['source_id'],
            payload=observation, digest=pipeline.digest(observation))
        return payload

    def test_state_uses_approved_ids_exact_categories_and_supported_ai_links_only(self):
        self.ai_result()
        state = self.state()
        items = {item['id']: item for item in state['items']}
        self.assertEqual(set(items), {field['id'] for section in self.schema['sections'] for field in section['fields']})
        self.assertEqual(items['foundation']['category'], 'Civil')
        self.assertEqual(items['manufacturer']['category'], 'Electrical')
        self.assertTrue(items['manufacturer']['category_known'])
        self.assertIn('visible manufacturer label', items['manufacturer']['instruction'])
        self.assertEqual(items['special_note']['category'], '')
        self.assertFalse(items['special_note']['category_known'])
        self.assertEqual(self.pairs(state), {(self.photos['Electrical'].pk, 'manufacturer')})
        self.assertEqual(state['links'][0]['state'], 'ai_suggested')
        self.assertEqual(state['counts']['total'], 4)
        self.assertEqual(state['counts']['assigned'], 1)
        self.assertEqual(state['counts']['unassigned'], 3)
        self.assertIn(self.photos[''].pk, state['unassigned_photo_ids'])
        self.assertTrue(state['observations'][str(self.photos['Electrical'].pk)])
        self.assertTrue(all(not item.get('accepted') for item in state['items']))

    def test_confirmed_photo_link_does_not_accept_required_photo_or_engineering_point(self):
        before = self.state()
        state = self.confirm(self.photos['Civil'], 'civil_photo')
        item = next(item for item in state['items'] if item['id'] == 'civil_photo')
        self.assertFalse(item.get('accepted'))
        self.assertEqual(item.get('value'), next(item for item in before['items'] if item['id'] == 'civil_photo').get('value'))
        self.assertEqual(state['links'][0]['state'], 'qa_confirmed')
        self.assertFalse(state['can_complete'])
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
        self.assertEqual(self.checklist.answer_data, {})
        self.assertFalse(self.revision.processing_events.filter(action='qa_complete').exists())

    def test_reassignment_removes_only_explicit_old_link_and_preserves_other_valid_link(self):
        photo = self.photos['Electrical']
        self.confirm(photo, 'manufacturer')
        self.confirm(photo, 'civil_photo')
        response = self.mutate('reassign_link', photo_id=photo.pk,
            from_field_id='manufacturer', to_field_id='model')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.pairs(response.json()), {(photo.pk, 'civil_photo'), (photo.pk, 'model')})
        photo.refresh_from_db()
        self.assertEqual(photo.group, 'Electrical')
        self.assertEqual(response.json()['counts']['assigned'], 1)

    def test_photo_becomes_globally_unassigned_only_after_its_last_link_is_removed(self):
        photo = self.photos['Civil']
        self.confirm(photo, 'foundation')
        self.confirm(photo, 'civil_photo')
        first = self.mutate('unlink', photo_id=photo.pk, field_id='foundation')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertNotIn(photo.pk, first.json()['unassigned_photo_ids'])
        second = self.mutate('unlink', photo_id=photo.pk, field_id='civil_photo')
        self.assertEqual(second.status_code, 200, second.content)
        self.assertIn(photo.pk, second.json()['unassigned_photo_ids'])
        self.assertEqual(second.json()['counts']['unassigned'], 4)

    def test_confirming_every_photo_keeps_zero_unassigned_and_does_not_duplicate_links(self):
        for photo in self.photos.values():
            self.confirm(photo, 'manufacturer')
        state = self.state()
        count = self.revision.processing_events.count()
        self.assertEqual(state['unassigned_photo_ids'], [])
        self.assertEqual(state['counts']['unassigned'], 0)
        self.confirm(self.photos['Tower'], 'manufacturer')
        refreshed = self.state()
        self.assertEqual(len(refreshed['links']), 4)
        self.assertEqual(self.revision.processing_events.count(), count)
        self.assertEqual(refreshed['unassigned_photo_ids'], [])

    def test_cross_category_assignment_preserves_source_group_bytes_and_submission(self):
        photo = self.photos['Civil']
        raw = Path(photo.original.path).read_bytes()
        snapshot = deepcopy(self.revision.snapshot)
        self.confirm(photo, 'manufacturer')
        photo.refresh_from_db(); self.revision.refresh_from_db()
        self.assertEqual(photo.group, 'Civil')
        self.assertEqual(Path(photo.original.path).read_bytes(), raw)
        self.assertEqual(self.revision.snapshot, snapshot)
        self.assertEqual(next(p for p in self.revision.snapshot['photos'] if p['id'] == photo.pk)['group'], 'Civil')

    def test_stale_link_save_leaves_prior_assignments_counts_and_audit_unchanged(self):
        old = self.state()
        self.confirm(self.photos['Electrical'], 'manufacturer')
        before = self.state()
        events = self.revision.processing_events.count()
        stale = self.mutate('confirm_link', state=old, photo_id=self.photos['Civil'].pk, field_id='foundation')
        self.assertEqual(stale.status_code, 409, stale.content)
        after = self.state()
        self.assertEqual(after['links'], before['links'])
        self.assertEqual(after['counts'], before['counts'])
        self.assertEqual(self.revision.processing_events.count(), events)

    def test_foreign_photos_unknown_points_and_wrong_same_project_reviewers_cannot_mutate(self):
        before = self.state()
        for photo_id, field in [(self.photo.pk, 'manufacturer'),
                                (self.photos['Civil'].pk, 'invented_point')]:
            denied = self.mutate('confirm_link', photo_id=photo_id, field_id=field)
            self.assertEqual(denied.status_code, 409, denied.content)
        for actor in (self.engineer, self.admin, self.lead, self.customer,
                      self.person('unassigned_qa', Profile.Roles.QUALITY_ENGINEER)):
            denied = self.mutate('confirm_link', actor=actor, state=before,
                photo_id=self.photos['Civil'].pk, field_id='foundation')
            self.assertIn(denied.status_code, (403, 404), denied.content)
        self.assertEqual(self.state()['links'], before['links'])
        self.assertEqual(self.revision.processing_events.count(), 1)  # capture_submitted only

    def test_old_revision_is_rejected_even_when_review_payload_digest_is_identical(self):
        old = self.state()
        self.route(self.quality, 'reject')
        self.client.force_login(self.engineer)
        self.submit_capture()
        current = self.state()
        self.assertNotEqual(old['revision_id'], current['revision_id'])
        self.assertEqual(old['review_digest'], current['review_digest'])
        old_page = {**current, 'revision_id': old['revision_id']}
        denied = self.mutate('confirm_link', state=old_page,
            photo_id=self.photos['Civil'].pk, field_id='foundation')
        self.assertEqual(denied.status_code, 409, denied.content)
        self.assertEqual(self.state()['links'], [])

    def test_display_reorder_persists_without_changing_template_sources_or_decisions(self):
        before = self.state()
        schema = deepcopy(self.checklist.schema_snapshot)
        snapshot = deepcopy(self.revision.snapshot)
        technical = self.checklist.submission_revisions.get()
        signature = technical.digest
        original = before['display_order']['Civil']
        response = self.mutate('reorder', category='Civil', field_ids=list(reversed(original)))
        self.assertEqual(response.status_code, 200, response.content)
        refreshed = self.state()
        self.assertEqual(refreshed['display_order']['Civil'], list(reversed(original)))
        self.assertEqual(refreshed['review_digest'], before['review_digest'])
        self.assertEqual(refreshed['source_digest'], before['source_digest'])
        self.assertEqual(refreshed['links'], before['links'])
        self.checklist.refresh_from_db(); self.revision.refresh_from_db(); technical.refresh_from_db()
        self.assertEqual(self.checklist.schema_snapshot, schema)
        self.assertEqual(self.revision.snapshot, snapshot)
        self.assertEqual(technical.digest, signature)
        self.assertEqual(technical.decisions.count(), 1)
        event = self.revision.processing_events.order_by('-pk').first()
        self.assertEqual(event.actor_id, self.quality.pk)
        self.assertIsNotNone(event.created_at)

    def test_display_order_rejects_cross_category_ids_duplicates_missing_ids_and_not_assigned(self):
        before = self.state()
        original = before['display_order']['Civil']
        cases = [[original[0], 'manufacturer'], [original[0], original[0]],
                 [original[0]], [*original, 'Not Assigned']]
        events = self.revision.processing_events.count()
        for ids in cases:
            with self.subTest(field_ids=ids):
                response = self.mutate('reorder', category='Civil', field_ids=ids)
                self.assertEqual(response.status_code, 409, response.content)
        after = self.state()
        self.assertEqual(after['display_order'], before['display_order'])
        self.assertEqual(after['review_digest'], before['review_digest'])
        self.assertEqual(self.revision.processing_events.count(), events)

    def test_display_order_digest_is_independent_of_link_content_changes(self):
        old = self.state()
        self.confirm(self.photos['Civil'], 'foundation')
        response = self.mutate('reorder', state=old, category='Civil',
            field_ids=list(reversed(old['display_order']['Civil'])))
        self.assertEqual(response.status_code, 200, response.content)
        stale = self.mutate('reorder', state=old, category='Civil', field_ids=old['display_order']['Civil'])
        self.assertEqual(stale.status_code, 409, stale.content)

    def test_late_ai_preserves_qa_reassignment_and_explicit_unlink(self):
        photo = self.photos['Electrical']
        self.confirm(photo, 'manufacturer')
        moved = self.mutate('reassign_link', photo_id=photo.pk,
            from_field_id='manufacturer', to_field_id='foundation')
        self.assertEqual(moved.status_code, 200, moved.content)
        self.ai_result()
        state = self.state()
        self.assertEqual(self.pairs(state), {(photo.pk, 'foundation')})
        self.assertEqual(state['links'][0]['state'], 'qa_confirmed')
        unlinked = self.mutate('unlink', photo_id=photo.pk, field_id='foundation')
        self.assertEqual(unlinked.status_code, 200, unlinked.content)
        self.assertIn(photo.pk, self.state()['unassigned_photo_ids'])

    def test_manual_matching_remains_available_during_realistic_failed_ai_state(self):
        job = self.revision.processing_job
        job.status = 'failed'; job.error = 'Synthetic disconnected local model'
        job.save(update_fields=['status', 'error'])
        state = self.confirm(self.photos['Civil'], 'foundation')
        self.assertEqual(state['ai']['status'], 'failed')
        self.assertEqual(self.pairs(state), {(self.photos['Civil'].pk, 'foundation')})
        self.assertFalse(next(item for item in state['items'] if item['id'] == 'foundation').get('accepted'))

    def test_reassignment_database_failure_rolls_back_both_link_and_count_changes(self):
        photo = self.photos['Electrical']
        self.confirm(photo, 'manufacturer')
        before = self.state()
        events = self.revision.processing_events.count()
        create = SurveyProcessingEvent.objects.create
        link_writes = []
        def fail_second_link(**kwargs):
            if kwargs.get('action') == 'qa_link':
                link_writes.append(kwargs)
                if len(link_writes) == 2:
                    raise RuntimeError('Synthetic database write interruption')
            return create(**kwargs)
        self.client.raise_request_exception = False
        with patch.object(SurveyProcessingEvent.objects, 'create', side_effect=fail_second_link):
            response = self.mutate('reassign_link', photo_id=photo.pk,
                from_field_id='manufacturer', to_field_id='model')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(len(link_writes), 2)
        after = self.state()
        self.assertEqual(after['links'], before['links'])
        self.assertEqual(after['counts'], before['counts'])
        self.assertEqual(self.revision.processing_events.count(), events)

    def test_old_map_action_does_not_implicitly_accept_a_photo_requirement(self):
        response = self.mutate('map', field_id='civil_photo', photo_ids=[self.photos['Civil'].pk])
        self.assertEqual(response.status_code, 200, response.content)
        item = next(item for item in response.json()['items'] if item['id'] == 'civil_photo')
        self.assertFalse(item.get('accepted'))
        self.assertIn((self.photos['Civil'].pk, 'civil_photo'), self.pairs(response.json()))

    def test_missing_schema_and_template_exposes_configuration_error_without_inventing_items(self):
        self.route(self.quality, 'reject')
        self.checklist.checklist_template = None
        self.checklist.schema_snapshot = {}
        self.checklist.save(update_fields=['checklist_template', 'schema_snapshot'])
        self.client.force_login(self.engineer)
        self.submit_capture()
        state = self.state()
        self.assertTrue(state['config_error'])
        self.assertEqual(state['items'], [])
        self.assertEqual(len(state['photos']), 4)
        self.assertEqual(state['links'], [])
        self.assertEqual(state['counts']['unassigned'], 4)
        self.assertFalse(state['can_complete'])
        denied = self.mutate('confirm_link', photo_id=self.photos['Civil'].pk, field_id='invented_default')
        self.assertEqual(denied.status_code, 409, denied.content)

    def test_approved_qa_links_are_locked_until_existing_authorized_return(self):
        for field, value, photo_ids in [('contact', 'Synthetic recorded contact', []),
                                        ('civil_photo', None, [self.photos['Civil'].pk, self.photos['Tower'].pk])]:
            response = self.mutate('answer', field_id=field, value=value, photo_ids=photo_ids)
            self.assertEqual(response.status_code, 200, response.content)
        completed = self.mutate('complete')
        self.assertEqual(completed.status_code, 200, completed.content)
        self.route(self.quality, 'approve')
        state = self.state()
        for name, values in [('confirm_link', {'field_id': 'foundation', 'photo_id': self.photos['Civil'].pk}),
                             ('reorder', {'category': 'Civil', 'field_ids': state['display_order']['Civil']})]:
            denied = self.mutate(name, state=state, **values)
            self.assertEqual(denied.status_code, 403, denied.content)
        self.route(self.lead, 'reject')
        reopened = self.confirm(self.photos['Civil'], 'foundation')
        self.assertIn((self.photos['Civil'].pk, 'foundation'), self.pairs(reopened))

    def test_ai_source_must_correspond_to_this_exact_approved_field_not_another_same_photo_finding(self):
        photo = self.photos['Electrical']
        finding = {'field_hint': 'manufacturer', 'value': 'SyntheticCo', 'confidence': 'high',
            'source_id': 'photo:' + str(photo.pk), 'reference': photo.filename}
        payload = pipeline.prepare_checklist(self.revision.snapshot,
            {'findings': [finding], 'missing': [], 'conflicts': []})
        manufacturer = next(item for item in payload['checklist_items'] if item['id'] == 'manufacturer')
        contact = next(item for item in payload['checklist_items'] if item['id'] == 'contact')
        # A malformed association copied another point's sources and answer.
        # High confidence on that photo alone must not validate the wrong ID.
        contact.update(value='SyntheticCo', proposed_answer='SyntheticCo', confidence='high',
            status='Needs review', conflict=False, sources=deepcopy(manufacturer['sources']))
        SurveyProcessingResult.objects.create(revision=self.revision, payload=payload, digest=pipeline.digest(payload))
        state = self.state()
        self.assertEqual(self.pairs(state), {(photo.pk, 'manufacturer')})
        self.assertFalse(next(item for item in state['items'] if item['id'] == 'contact')['sources'])
        self.assertEqual(state['counts']['suggested'], 1)

    def test_original_and_crop_are_one_photo_link_and_cannot_satisfy_two_photo_minimum(self):
        photo = self.photos['Civil']
        findings = []
        for source_id, reference in [('photo:' + str(photo.pk), 'Original source'),
                                     ('photo:' + str(photo.pk) + ':crop:1', 'Targeted crop1')]:
            finding = {'field_hint': 'civil_photo', 'value': 'Visible synthetic foundation subject',
                'confidence': 'high', 'source_id': source_id, 'reference': reference}
            findings.append(finding)
            observation = {'source_id': source_id, 'reference': reference, 'findings': [finding]}
            SurveySourceAnalysis.objects.create(revision=self.revision, source_id=source_id,
                payload=observation, digest=pipeline.digest(observation))
        payload = pipeline.prepare_checklist(self.revision.snapshot,
            {'findings': findings, 'missing': [], 'conflicts': []})
        SurveyProcessingResult.objects.create(revision=self.revision, payload=payload, digest=pipeline.digest(payload))
        state = self.state()
        self.assertEqual(self.pairs(state), {(photo.pk, 'civil_photo')})
        self.assertEqual(len(state['links']), 1)
        item = next(item for item in state['items'] if item['id'] == 'civil_photo')
        # Original and crop references remain traceable, but refer to one photo.
        self.assertEqual({source['source_id'].split(':')[1] for source in item['sources']}, {str(photo.pk)})
        self.assertEqual(len(state['observations'][str(photo.pk)]), 2)
        self.assertEqual(state['counts']['assigned'], 1)
        self.assertEqual(state['counts']['suggested'], 1)
        self.assertTrue(any('Foundation source evidence' in value and '2 distinct' in value for value in state['missing']))
        self.assertFalse(state['can_complete'])

    def test_shared_client_projection_excludes_optional_ai_answer_sources_and_diagnostics(self):
        """Two required human answers must not publish an optional AI-only value."""
        source = self.photos['Electrical']
        finding = {'field_hint': 'manufacturer', 'value': 'PRIVATE_AI_ONLY_SENTINEL',
            'confidence': 'high', 'reason': 'PRIVATE_AI_MATCH_REASON',
            'source_id': 'photo:' + str(source.pk), 'reference': source.filename}
        payload = pipeline.prepare_checklist(self.revision.snapshot,
            {'findings': [finding], 'missing': [], 'conflicts': []})
        SurveyProcessingResult.objects.create(revision=self.revision, payload=payload, digest=pipeline.digest(payload))
        observation = {'source_id': finding['source_id'], 'reference': source.filename,
            'findings': [finding], 'provider': 'PRIVATE_AI_OBSERVATION_PROVIDER'}
        SurveySourceAnalysis.objects.create(revision=self.revision, source_id=finding['source_id'],
            payload=observation, digest=pipeline.digest(observation))
        job = self.revision.processing_job
        job.status = 'failed'
        job.error = 'PRIVATE_AI_FAILED_JOB_DIAGNOSTIC'
        job.save(update_fields=['status', 'error'])
        for field, value, ids in [('contact', 'Client-facing recorded contact', []),
                                  ('civil_photo', None, [self.photos['Civil'].pk, self.photos['Tower'].pk])]:
            accepted = self.mutate('answer', field_id=field, value=value, photo_ids=ids)
            self.assertEqual(accepted.status_code, 200, accepted.content)
        completed = self.mutate('complete')
        self.assertEqual(completed.status_code, 200, completed.content)
        self.route(self.quality, 'approve')
        self.route(self.lead, 'approve')
        client = self.state(self.customer)
        encoded = json.dumps(client)
        for private in ('PRIVATE_AI_ONLY_SENTINEL', 'PRIVATE_AI_MATCH_REASON', 'PRIVATE_AI_OBSERVATION_PROVIDER',
                        'PRIVATE_AI_FAILED_JOB_DIAGNOSTIC'):
            self.assertNotIn(private, encoded)
        optional = next(item for item in client['items'] if item['id'] == 'manufacturer')
        self.assertFalse(optional.get('accepted'))
        self.assertIsNone(optional.get('value'))
        self.assertIsNone(optional.get('proposed_answer'))
        self.assertEqual(optional.get('sources', []), [])
        self.assertIsNone(optional.get('confidence'))
        self.assertFalse(optional.get('reason'))
        self.assertFalse(client.get('observations'))
        self.assertFalse(client.get('matching_history'))
        self.assertEqual(next(item for item in client['items'] if item['id'] == 'contact')['value'],
                         'Client-facing recorded contact')
        accepted_evidence = next(item for item in client['items'] if item['id'] == 'civil_photo')
        self.assertEqual({int(ref['source_id'].split(':')[1]) for ref in accepted_evidence['sources']},
                         {self.photos['Civil'].pk, self.photos['Tower'].pk})
        state = self.client.get(reverse('photo_state', args=[self.checklist.pk]))
        self.assertEqual(state.status_code, 200, state.content)
        self.assertNotIn('PRIVATE_AI_ONLY_SENTINEL', state.content.decode())
        self.assertEqual({photo['id'] for photo in state.json()['photos']}, {photo.pk for photo in self.photos.values()})
        direct_capture = self.client.get(reverse('photo_capture_state', args=[self.checklist.pk]))
        self.assertEqual(direct_capture.status_code, 403)
        self.assertNotIn('PRIVATE_AI_FAILED_JOB_DIAGNOSTIC', direct_capture.content.decode())
        original = self.client.get(reverse('photo_evidence',
            args=[self.checklist.pk, self.photos['Civil'].pk, 'original']))
        self.assertEqual(original.status_code, 200)
        self.assertEqual(b''.join(original.streaming_content), Path(self.photos['Civil'].original.path).read_bytes())
        original.close()
        self.client.force_login(self.engineer)
        engineer_capture = self.client.get(reverse('photo_capture_state', args=[self.checklist.pk]))
        self.assertEqual(engineer_capture.status_code, 200, engineer_capture.content)
        self.assertNotIn('PRIVATE_AI_FAILED_JOB_DIAGNOSTIC', engineer_capture.content.decode())
        self.assertNotIn('PRIVATE_AI_ONLY_SENTINEL', engineer_capture.content.decode())
        self.assertEqual(engineer_capture.json()['ai'], {'status': 'submitted'})
        self.assertEqual({photo['id'] for photo in engineer_capture.json()['photos']},
                         {photo.pk for photo in self.photos.values()})

    def test_client_return_reopens_only_current_qa_edit_locks_and_preserves_old_signatures(self):
        for field, value, ids in [('contact', 'Synthetic recorded contact', []),
                                  ('civil_photo', None, [self.photos['Civil'].pk, self.photos['Tower'].pk])]:
            saved = self.mutate('answer', field_id=field, value=value, photo_ids=ids)
            self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(self.mutate('complete').status_code, 200)
        self.route(self.quality, 'approve')
        self.route(self.lead, 'approve')
        self.assertTrue(self.checklist.section_approvals)
        technical = self.checklist.submission_revisions.get()
        original_snapshot = deepcopy(technical.snapshot)
        original_digest = technical.digest
        prior_signatures = list(technical.decisions.values('id', 'actor_id', 'action', 'created_at'))
        self.route(self.customer, 'reject')
        self.assertTrue(self.checklist.section_approvals)
        denied = self.mutate('confirm_link', photo_id=self.photos['Electrical'].pk, field_id='civil_photo')
        self.assertEqual(denied.status_code, 403, denied.content)
        self.route(self.lead, 'return')
        self.assertEqual(self.checklist.review_route_record.stage, 'quality_engineer')
        self.assertFalse(self.checklist.section_approvals)
        changed = self.mutate('reassign_link', photo_id=self.photos['Civil'].pk,
            from_field_id='civil_photo', to_field_id='foundation')
        self.assertEqual(changed.status_code, 200, changed.content)
        self.confirm(self.photos['Electrical'], 'civil_photo')
        self.assertEqual(self.mutate('complete').status_code, 200)
        self.route(self.quality, 'clarify')
        self.route(self.lead, 'approve')
        self.route(self.customer, 'approve')
        self.assertEqual(self.checklist.review_route_record.stage, 'closed')
        self.assertTrue(self.checklist.section_approvals)
        technical.refresh_from_db(); self.checklist.refresh_from_db()
        self.assertEqual(technical.snapshot, original_snapshot)
        self.assertEqual(technical.digest, original_digest)
        self.assertEqual(self.checklist.answer_data, {})
        for signature in prior_signatures:
            self.assertEqual(technical.decisions.values('id', 'actor_id', 'action', 'created_at').get(pk=signature['id']), signature)

    def test_unlinked_current_source_does_not_fall_back_to_retained_legacy_field_image(self):
        self.route(self.quality, 'reject')
        photo = self.photos['Electrical']
        legacy_images = {'manufacturer': [photo.original.name]}
        self.checklist.image_data = deepcopy(legacy_images)
        self.checklist.save(update_fields=['image_data'])
        original_bytes = Path(photo.original.path).read_bytes()
        self.client.force_login(self.engineer)
        self.submit_capture()
        self.revision = self.checklist.processing_revisions.order_by('-number').first()
        technical = self.checklist.submission_revisions.order_by('-number').first()
        source_snapshot = deepcopy(technical.snapshot)
        source_digest = technical.digest
        self.confirm(photo, 'manufacturer')
        unlinked = self.mutate('unlink', photo_id=photo.pk, field_id='manufacturer')
        self.assertEqual(unlinked.status_code, 200, unlinked.content)
        self.assertFalse(next(item for item in unlinked.json()['items'] if item['id'] == 'manufacturer')['sources'])
        stale_field_source = self.client.get(reverse('custom_checklist_photo',
            args=[self.checklist.pk, 'manufacturer', 0]))
        self.assertEqual(stale_field_source.status_code, 404,
                         'Current field sources must not fall back to a link QA explicitly removed')
        report = self.client.get(reverse('custom_checklist_download', args=[self.checklist.pk]))
        self.assertEqual(report.status_code, 200)
        workbook = load_workbook(BytesIO(report.content))
        self.assertEqual(len(workbook['Site survey']._images), 0)
        workbook.close()
        self.checklist.refresh_from_db(); technical.refresh_from_db()
        self.assertEqual(self.checklist.image_data, legacy_images)
        self.assertEqual(technical.snapshot, source_snapshot)
        self.assertEqual(technical.digest, source_digest)
        self.assertEqual(technical.snapshot['field_images'], legacy_images)
        self.assertEqual(Path(photo.original.path).read_bytes(), original_bytes)
        retained_source = self.client.get(reverse('photo_evidence', args=[self.checklist.pk, photo.pk, 'original']))
        self.assertEqual(retained_source.status_code, 200)
        self.assertEqual(b''.join(retained_source.streaming_content), original_bytes)
        retained_source.close()
