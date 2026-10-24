"""Real frozen workspace data, separate from presentation and AI inference."""
from copy import deepcopy
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings

from . import category_intake, qa_matching
from .models import PhotoEvidence
from . import test_engineer_category_submission_acceptance as fixtures


@override_settings(ROOT_URLCONF='checklist.urls_local')
class ReviewWorkspaceProjectionTests(SimpleTestCase):
    def project(self,metadata):
        photo={'id':7,'filename':'source.jpg','group':'Civil','metadata':metadata}
        snapshot={'photos':[photo]}; before=deepcopy(snapshot)
        result=category_intake.photos(snapshot,SimpleNamespace(pk=3))[0]
        self.assertEqual(snapshot,before)
        return result

    def test_capture_projection_whitelists_only_recorded_time_and_coordinates(self):
        result=self.project({'captured_at':'2026:10:24 09:15:00',
            'gps':{'latitude':0,'longitude':0,'private_receiver':'SECRET'},
            'private_path':'SECRET','token':'SECRET','width':4000})
        self.assertEqual(result['metadata'],{'captured_at':'2026:10:24 09:15:00',
            'gps':{'latitude':0,'longitude':0}})
        self.assertNotIn('SECRET',str(result))

    def test_absent_or_invalid_capture_facts_remain_absent(self):
        for metadata in ({},None,[],{'captured_at':None,'gps':None},
                {'captured_at':12,'gps':{'latitude':True,'longitude':40}},
                {'gps':{'latitude':91,'longitude':40}},
                {'gps':{'latitude':10**1000,'longitude':40}},
                {'gps':{'latitude':24,'longitude':float('nan')}},
                {'gps':{'latitude':24}}):
            with self.subTest(metadata=metadata):
                self.assertEqual(self.project(metadata)['metadata'],{})

    def test_hierarchy_uses_the_approved_group_not_words_in_the_title(self):
        revision=SimpleNamespace(snapshot={'schema':{'sections':[
            {'id':'real-section','title':'Tower words do not define hierarchy',
             'category':'Civil','group':'Approved foundation grouping',
             'fields':[{'id':'stable-point','label':'Recorded requirement','type':'text'}]}]}})
        catalog=qa_matching.catalog(revision)
        self.assertEqual(catalog['stable-point']['category'],'Civil')
        self.assertEqual(catalog['stable-point']['group'],'Approved foundation grouping')
        self.assertEqual(catalog['stable-point']['section_id'],'real-section')


@override_settings(SECRET_KEY='isolated-review-workspace',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewWorkspaceHTTPTests(TestCase):
    setUp=fixtures.EngineerCategorySubmissionAcceptanceTests.setUp
    person=fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw=fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    post=fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=fixtures.EngineerCategorySubmissionAcceptanceTests.state
    upload=fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    qa_state=fixtures.EngineerCategorySubmissionAcceptanceTests.qa_state

    def test_approved_section_exposes_the_existing_lock_before_a_save_is_attempted(self):
        photos,_=self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        self.checklist.refresh_from_db()
        self.checklist.section_approvals={self.schema['sections'][0]['id']:{'approved':True}}
        self.checklist.save(update_fields=['section_approvals'])
        state=self.qa_state()
        contact=next(item for item in state['items'] if item['id']=='contact')
        self.assertIs(contact.get('locked'),True)
        denied=self.post('photo_capture_review_action',{
            'action':'confirm_link','field_id':'contact','photo_id':photos[0]['id'],
            'revision_id':state['revision_id'],'source_digest':state['source_digest'],
            'expected_review_digest':state['review_digest'],
            'reason':'An approved section must remain locked.'},actor=self.quality)
        self.assertEqual(denied.status_code,409)
        self.assertFalse(self.checklist.processing_revisions.get().processing_events.filter(action='qa_link').exists())

    def test_review_uses_frozen_photo_facts_and_actual_template_identity(self):
        photos,_=self.upload('Civil')
        captured={'captured_at':'2026:10:24 10:30:00',
            'gps':{'latitude':24.7,'longitude':46.6},'private_path':'NOT PUBLIC'}
        PhotoEvidence.objects.filter(pk=photos[0]['id']).update(metadata=captured)
        response,_=self.submit();self.assertEqual(response.status_code,201,response.content)
        revision=self.checklist.processing_revisions.get();frozen=deepcopy(revision.snapshot)
        PhotoEvidence.objects.filter(pk=photos[0]['id']).update(metadata={
            'captured_at':'2030:01:01 00:00:00','gps':{'latitude':1,'longitude':2}})
        state=self.qa_state()
        self.assertEqual(state['photos'][0]['metadata'],{
            'captured_at':captured['captured_at'],'gps':captured['gps']})
        self.assertEqual(state['template'],{'id':self.template.pk,
            'name':self.template.name,'version':self.template.version})
        self.assertNotIn('NOT PUBLIC',str(state['photos']))
        revision.refresh_from_db();self.assertEqual(revision.snapshot,frozen)

    def test_shared_photo_counts_stay_unique_and_link_counts_stay_distinct(self):
        from django.urls import reverse
        photos,_=self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        state=self.qa_state()
        for ident in ['manufacturer','contact']:
            response=self.post('photo_capture_review_action',{
                'action':'confirm_link','field_id':ident,'photo_id':photos[0]['id'],
                'revision_id':state['revision_id'],'source_digest':state['source_digest'],
                'expected_review_digest':state['review_digest'],
                'reason':'Checked the same submitted photo against both requirements.'},actor=self.quality)
            self.assertEqual(response.status_code,200,response.content)
            state=response.json()
        self.assertEqual(state['counts'],{'total':1,'assigned':1,'unassigned':0,
            'suggested':0,'confirmed':2})
        self.assertFalse(any(item['accepted'] for item in state['items']))
        self.client.force_login(self.engineer)
        denied=self.client.get(reverse('photo_capture_review_state',args=[self.checklist.pk]))
        self.assertEqual(denied.status_code,403)
