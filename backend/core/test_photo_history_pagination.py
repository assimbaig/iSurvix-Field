"""Bounded authorized history must retain source links, jobs and actionable drafts."""
from copy import deepcopy

from django.test import Client, TestCase, override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from . import test_survey_processing as fixtures
from .models import PhotoDraft, PhotoJob, Profile, Project


@override_settings(SECRET_KEY='isolated-photo-history-pages',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PhotoHistoryPaginationTests(TestCase):
    setUp = fixtures.SurveyProcessingTests.setUp
    person = fixtures.SurveyProcessingTests.person
    add_photo = fixtures.SurveyProcessingTests.add_photo

    def history(self):
        active = PhotoJob.objects.create(checklist=self.checklist,
            requested_by=self.engineer, model='synthetic', schema=self.checklist.schema_snapshot,
            status='running', total=2, progress={'stage': 'matching_checklist'})
        active.photos.add(self.photo, self.photo2)
        jobs = PhotoJob.objects.bulk_create([PhotoJob(checklist=self.checklist,
            requested_by=self.engineer, model='synthetic', schema=self.checklist.schema_snapshot,
            status='cancelled') for _ in range(120)])
        drafts = PhotoDraft.objects.bulk_create([PhotoDraft(job=job, photo=self.photo,
            field_id='manufacturer', label='Saved proposal', value='Reported maker',
            reason='Retained observation', uncertainty='high', status='pending' if index < 2 else 'accepted')
            for index, job in enumerate(jobs)])
        self.client.force_login(self.admin)
        return active, jobs, drafts

    def test_initial_payload_is_bounded_and_prioritizes_old_active_and_pending_records(self):
        active, jobs, drafts = self.history()
        response = self.client.get(reverse('photo_state', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertLessEqual(len(payload['jobs']), 50)
        self.assertLessEqual(len(payload['drafts']), 50)
        self.assertEqual(payload['jobs'][0]['id'], active.pk)
        self.assertEqual({row['id'] for row in payload['drafts'][:2]}, {d.pk for d in drafts[:2]})
        self.assertEqual(payload['history']['jobs']['total'], 121)
        self.assertEqual(payload['history']['drafts']['total'], 120)
        self.assertTrue(payload['history']['jobs']['has_more'])
        self.assertEqual(payload['analysis']['active_job_count'], 1)
        self.assertEqual(payload['analysis']['workflow']['stage'], 'matching_checklist')
        self.assertLess(len(response.content), 100_000)

    def test_following_scoped_cursors_returns_every_record_once_without_changing_saved_rows(self):
        self.history()
        initial = self.client.get(reverse('photo_state', args=[self.checklist.pk])).json()
        expected_jobs = set(self.checklist.photo_jobs.values_list('pk', flat=True))
        expected_drafts = set(PhotoDraft.objects.filter(job__checklist=self.checklist).values_list('pk', flat=True))
        for collection, expected in [('jobs', expected_jobs), ('drafts', expected_drafts)]:
            seen = [row['id'] for row in initial[collection]]
            page = initial['history'][collection]
            while page['has_more']:
                response = self.client.get(page['next_url'])
                self.assertEqual(response.status_code, 200, response.content)
                data = response.json()
                self.assertNotIn('photos', data, 'History fetch must not resend the full photo state')
                self.assertLessEqual(len(data[collection]), 50)
                seen.extend(row['id'] for row in data[collection])
                page = data['history'][collection]
            self.assertEqual(set(seen), expected)
            self.assertEqual(len(seen), len(expected))
        self.assertEqual(set(self.checklist.photo_jobs.values_list('pk', flat=True)), expected_jobs)
        self.assertEqual(set(PhotoDraft.objects.filter(job__checklist=self.checklist).values_list('pk', flat=True)), expected_drafts)
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.section_approvals, {})
        self.assertEqual(self.checklist.answer_data['custom']['contact'], 'Synthetic contact')

    def test_history_parameters_fail_safely_and_foreign_projects_cannot_page_history(self):
        self.history()
        url = reverse('photo_state', args=[self.checklist.pk])
        for query in [{'history': 'secrets'}, {'history': 'jobs', 'cursor': '-1:1'},
                      {'history': 'drafts', 'cursor': '0:-1'}, {'history': 'jobs', 'cursor': '3:1'},
                      {'history': 'jobs', 'cursor': '0:' + '9' * 100}, {'history': 'jobs', 'cursor': 'garbage'}]:
            with self.subTest(query=query):
                response = self.client.get(url, query)
                self.assertEqual(response.status_code, 400)
                self.assertIn('no-store', response.get('Cache-Control', ''))
        project = Project.objects.create(name='Foreign synthetic history', company=self.company)
        outsider = self.person('foreign_history', Profile.Roles.ADMIN, project)
        browser = Client()
        browser.force_login(outsider)
        self.assertEqual(browser.get(url, {'history': 'jobs'}).status_code, 404)

    def test_more_than_one_page_of_queued_jobs_cannot_hide_an_older_running_job(self):
        active, _, _ = self.history()
        PhotoJob.objects.bulk_create([PhotoJob(checklist=self.checklist,
            requested_by=self.engineer, model='synthetic', schema=self.checklist.schema_snapshot,
            status='queued') for _ in range(65)])
        data = self.client.get(reverse('photo_state', args=[self.checklist.pk])).json()
        self.assertLessEqual(len(data['jobs']), 50)
        self.assertEqual(data['jobs'][0]['id'], active.pk)
        self.assertEqual(data['analysis']['active_job_count'], 66)
        self.assertEqual(data['analysis']['workflow']['stage'], 'matching_checklist')

    def test_latest_context_skips_incompatible_or_empty_rows_without_reading_answer_baselines(self):
        from .evidence_pipeline import latest_context
        context = {'rules_version': 'synthetic-retained-rules', 'model_version': 'synthetic'}
        compatible = dict(reversed(list(self.checklist.schema_snapshot.items())))
        PhotoJob.objects.create(checklist=self.checklist, model='synthetic',
            schema=compatible, progress={'evidence_context': context},
            baseline={'retained_answer': 'private answer must not be read for a context lookup'})
        PhotoJob.objects.bulk_create([PhotoJob(checklist=self.checklist, model='synthetic',
            schema=self.checklist.schema_snapshot, progress={},
            baseline={'retained_answer': 'x' * 5000}) for _ in range(120)])
        other = deepcopy(self.checklist.schema_snapshot)
        other['title'] = 'Incompatible published template'
        PhotoJob.objects.create(checklist=self.checklist, model='synthetic', schema=other,
            progress={'evidence_context': {'rules_version': 'wrong context'}})
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(latest_context(self.checklist), context)
        self.assertEqual(len(queries), 1)
        self.assertNotIn('"baseline"', queries[0]['sql'], 'Lookup must not fetch every historical answer snapshot')

