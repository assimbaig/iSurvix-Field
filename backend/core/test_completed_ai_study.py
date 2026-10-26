"""Completed studies are read-only and retain source/project/release boundaries."""
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_engineer_category_submission_acceptance as fixtures
from .survey_processing_models import SurveySourceAnalysis
from . import survey_processing as pipeline


@override_settings(SECRET_KEY='isolated-completed-study', ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CompletedStudyTests(TestCase):
    person=fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw=fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload=fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted=fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted

    def setUp(self):
        fixtures.EngineerCategorySubmissionAcceptanceTests.setUp(self)
        self.upload('Civil')
        self.submit()
        self.revision=self.assert_submitted()
        self.url=reverse('photo_completed_ai_study',args=[self.checklist.pk])

    def completed(self,note='SOURCE_ONLY_STUDY',digest=None):
        job=self.revision.processing_job
        job.status='ready_for_review'
        job.save(update_fields=['status'])
        photo=self.revision.snapshot['photos'][0]
        payload={'reference':photo['filename'],'findings':[{'component':'Synthetic breaker',
            'value':0,'unit':'A','notes':note,'evidence_quote':'0 A',
            'confidence':'high','defects':['Visible synthetic crack']}]}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:'+str(photo['id']),
            payload=payload,digest=digest or pipeline.digest(payload))

    def test_engineer_qa_lead_admin_share_same_readonly_table_without_changing_data(self):
        self.completed()
        before=(self.revision.processing_events.count(),self.revision.source_analyses.count())
        for actor in [self.engineer,self.quality,self.lead,self.admin]:
            with self.subTest(role=actor.profile.role):
                self.client.force_login(actor)
                response=self.client.get(self.url)
                self.assertEqual(response.status_code,200,response.content)
                self.assertContains(response,'qa-finding-table')
                self.assertContains(response,'SOURCE_ONLY_STUDY')
                self.assertContains(response,'0 A')
                self.assertContains(response,'Visible synthetic crack')
                self.assertNotContains(response,'confirm_candidate')
                self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertEqual((self.revision.processing_events.count(),self.revision.source_analyses.count()),before)

    def test_incomplete_study_is_honest_and_client_cannot_read_unreleased_private_observations(self):
        self.client.force_login(self.engineer)
        response=self.client.get(self.url)
        self.assertContains(response,'not complete')
        self.assertNotContains(response,'SOURCE_ONLY_STUDY')
        self.completed()
        self.client.force_login(self.customer)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,404)
        self.assertNotIn(b'SOURCE_ONLY_STUDY',response.content)

    def test_anonymous_foreign_revision_and_post_cannot_read_or_mutate(self):
        self.completed()
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code,302)
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.post(self.url,{}).status_code,405)
        self.assertEqual(self.client.get(self.url,{'revision_id':self.revision.pk+1}).status_code,404)
        foreign=self.person('foreign-study','ENGINEER')
        self.client.force_login(foreign)
        self.assertEqual(self.client.get(self.url).status_code,404)

    def test_released_client_view_has_same_format_but_only_accepted_information(self):
        from .models import Checklist
        from .review_route_models import ReviewRouteEvent
        from .survey_processing_models import SurveyProcessingEvent,SurveyDrawingSet
        self.completed()
        self.checklist.status=Checklist.Status.FINAL
        self.checklist.save(update_fields=['status'])
        route=self.checklist.review_route_record
        route.stage='client'
        route.save(update_fields=['stage'])
        ReviewRouteEvent.objects.create(route=route,sequence=route.events.count()+1,
            revision=route.revision,actor=self.lead,from_stage='team_lead',to_stage='client',
            action='approve',reason='Isolated released-view fixture only')
        pid=self.revision.snapshot['photos'][0]['id']
        package={'checklist_items':[{'id':'manufacturer','label':'Equipment manufacturer',
            'value':'RELEASED_SYNTHETIC_VALUE','accepted':True,
            'sources':[{'source_id':'photo:'+str(pid)}]}],'findings':[]}
        SurveyProcessingEvent.objects.create(revision=self.revision,actor=self.quality,
            action='qa_complete',payload={'package':package})
        SurveyDrawingSet.objects.create(revision=self.revision,edition=1,released=True,
            review_digest=pipeline.review_digest(package),geometry={},manifest={})
        self.client.force_login(self.customer)
        result=self.client.get(self.url)
        self.assertEqual(result.status_code,200,result.content)
        self.assertContains(result,'qa-finding-table')
        self.assertContains(result,'RELEASED_SYNTHETIC_VALUE')
        self.assertNotContains(result,'SOURCE_ONLY_STUDY')
        self.assertContains(result,'Only released QA-reviewed information')

    def test_corrupt_saved_analysis_returns_error_not_success_or_server_failure(self):
        self.completed(digest='invalid')
        self.client.force_login(self.quality)
        result=self.client.get(self.url)
        self.assertEqual(result.status_code,409)
        self.assertNotIn(b'SOURCE_ONLY_STUDY',result.content)

    def test_context_zero_coordinates_and_template_escaping_are_preserved(self):
        from .completed_ai_study import context_rows,observation_rows
        self.assertIn(('Coordinates','0, 0'),context_rows(self.checklist,{'id':1,
            'metadata':{'gps':{'latitude':0,'longitude':0}}}))
        self.assertIn(('Extracted value','0 A'),observation_rows({'value':0,'unit':'A'}))
        self.completed(note='<script>alert(1)</script>')
        self.client.force_login(self.quality)
        result=self.client.get(self.url)
        self.assertContains(result,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(result,'<script>alert(1)</script>')

    def test_actual_observation_defect_category_uses_only_recorded_defect_text(self):
        from .survey_evidence import Observation
        from .completed_ai_study import observation_rows
        finding=Observation(category='defect',component='Cabinet',value='Cracked panel',
            basis='visible',notes='Visible panel crack',evidence_quote='crack',confidence='high').model_dump()
        self.assertIn(('Defect / issue','Visible panel crack'),observation_rows(finding))
        finding['category']='equipment'
        self.assertIn(('Defect / issue','Not recorded'),observation_rows(finding))
