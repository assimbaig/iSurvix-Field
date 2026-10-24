"""QA cell edits are derived answers, never changes to Engineer source facts."""
from copy import deepcopy
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase, override_settings

from . import category_intake, survey_processing as pipeline
from . import test_engineer_category_submission_acceptance as fixture
from .survey_processing_models import SurveyProcessingResult
from .models import Checklist


@override_settings(SECRET_KEY='isolated-qa-site-table',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QASiteInformationTableTests(TestCase):
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

    def submitted(self):
        self.checklist.answer_data={'custom':{'contact':'Engineer recorded contact'}}
        self.checklist.save(update_fields=['answer_data'])
        self.upload('Civil');response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        self.revision=self.checklist.processing_revisions.get()
        return self.qa_state()

    def row(self,state,ident):
        return next(row for row in state['site_information_table']['rows'] if row['field_id']==ident)

    def test_table_shows_submitted_and_qa_values_in_one_flat_list(self):
        state=self.submitted();table=state['site_information_table']
        self.assertTrue(table['can_review'])
        contact=self.row(state,'contact')
        self.assertEqual(contact['submitted_value'],'Engineer recorded contact')
        self.assertEqual(contact['value'],'Engineer recorded contact')
        self.assertTrue(contact['can_edit']);self.assertTrue(contact['can_confirm'])
        source=next(row for row in table['rows'] if row['scope']=='site' and row['id']=='site_name')
        self.assertFalse(source['can_edit']);self.assertIsNone(source['field_id'])
        self.assertIn('Engineer',source['read_only_reason'])

    def test_value_cell_save_is_append_only_and_survives_refresh_without_source_mutation(self):
        state=self.submitted();before=deepcopy(self.revision.snapshot)
        response=self.qa_action('answer',field_id='contact',value='QA corrected contact',
            reason='Checked submitted site report contact.',preserve_evidence=True)
        self.assertEqual(response.status_code,200,response.content)
        corrected=self.row(response.json(),'contact')
        self.assertEqual(corrected['value'],'QA corrected contact')
        self.assertEqual(corrected['submitted_value'],'Engineer recorded contact')
        self.assertTrue(corrected['accepted'])
        refreshed=self.qa_state();self.assertEqual(self.row(refreshed,'contact'),corrected)
        self.assertEqual(refreshed['source_digest'],state['source_digest'])
        self.revision.refresh_from_db();self.assertEqual(self.revision.snapshot,before)
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.answer_data['custom']['contact'],'Engineer recorded contact')
        self.assertEqual(self.checklist.status,Checklist.Status.SUBMITTED)
        event=self.revision.processing_events.get(action='qa_answer')
        self.assertEqual(event.actor_id,self.quality.pk)

    def test_system_identity_is_confirmable_but_cannot_be_edited(self):
        state=self.submitted();site=self.row(state,'site_id')
        self.assertFalse(site['can_edit']);self.assertTrue(site['can_confirm'])
        result=self.qa_action('answer',field_id='site_id',value='FORGED-SITE',
            reason='Attempted identity edit',preserve_evidence=True)
        self.assertEqual(result.status_code,409,result.content)
        result=self.qa_action('answer',field_id='site_id',value=self.checklist.site_id,
            reason='Checked submitted site identity',preserve_evidence=True)
        self.assertEqual(result.status_code,200,result.content)
        self.assertTrue(self.row(result.json(),'site_id')['accepted'])
        self.checklist.refresh_from_db();self.assertEqual(self.checklist.site_id,'SYNTHETIC-CATEGORY-ACCEPTANCE')

    def test_source_only_cells_and_locked_sections_are_not_fake_editable_fields(self):
        self.submitted()
        result=self.qa_action('answer',field_id='site_name',value='Forged new field',
            reason='Unsupported source edit',preserve_evidence=True)
        self.assertEqual(result.status_code,409,result.content)
        self.checklist.refresh_from_db();self.checklist.section_approvals={'general':{'approved':True}}
        self.checklist.save(update_fields=['section_approvals'])
        state=self.qa_state();contact=self.row(state,'contact')
        self.assertFalse(contact['can_edit']);self.assertFalse(contact['can_confirm'])
        self.assertIn('locked',contact['read_only_reason'])
        result=self.qa_action('answer',field_id='contact',value='Should fail',
            reason='Approved section edit',preserve_evidence=True)
        self.assertEqual(result.status_code,409,result.content)
        self.assertFalse(self.revision.processing_events.filter(action='qa_answer').exists())

    def test_answer_cell_keeps_suggested_and_confirmed_photo_assignments_separate(self):
        self.submitted();photo=self.revision.snapshot['photos'][0]
        source={'source_id':f'photo:{photo["id"]}','reference':photo['filename']}
        finding={**source,'field_hint':'manufacturer','value':'SyntheticCo','confidence':'high'}
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':[finding],'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        before=self.qa_state();self.assertEqual(before['links'][0]['state'],'ai_suggested')
        result=self.qa_action('answer',field_id='manufacturer',value='QA corrected manufacturer',
            reason='Checked written manufacturer reference.',preserve_evidence=True)
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['links'],before['links'])
        self.assertEqual(result.json()['counts']['confirmed'],0)
        confirmed=self.qa_action('confirm_link',field_id='manufacturer',photo_id=photo['id'],
            reason='Independently inspected the photo match.')
        self.assertEqual(confirmed.status_code,200,confirmed.content)
        linked=confirmed.json()['links']
        result=self.qa_action('answer',field_id='manufacturer',value='Second QA value correction',
            reason='Rechecked the report value.',preserve_evidence=True)
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['links'],linked)

    def test_late_ai_still_adds_proposals_without_overwriting_cell_correction(self):
        self.submitted()
        result=self.qa_action('answer',field_id='manufacturer',value='Manual QA value',
            reason='Read submitted label while AI is still queued.',preserve_evidence=True)
        self.assertEqual(result.status_code,200,result.content)
        photo=self.revision.snapshot['photos'][0]
        source={'source_id':f'photo:{photo["id"]}','reference':photo['filename']}
        finding={**source,'field_hint':'manufacturer','value':'Different AI value','confidence':'high'}
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':[finding],'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        state=self.qa_state();self.assertEqual(self.row(state,'manufacturer')['value'],'Manual QA value')
        self.assertEqual(state['links'][0]['state'],'ai_suggested')
        self.assertEqual(state['counts']['confirmed'],0)

    def test_cell_only_flag_cannot_hide_a_request_to_change_photo_links(self):
        self.submitted();photo=self.revision.snapshot['photos'][0]
        result=self.qa_action('answer',field_id='contact',value='Mixed edit',photo_ids=[photo['id']],
            reason='Mixed value and evidence mutation',preserve_evidence=True)
        self.assertEqual(result.status_code,409,result.content)
        self.assertFalse(self.revision.processing_events.filter(action='qa_answer').exists())


class QASiteInformationTableUnitTests(SimpleTestCase):
    def checklist(self):
        return SimpleNamespace(status=Checklist.Status.SUBMITTED,section_approvals={},schema_snapshot={'sections':[
            {'id':'general','fields':[{'id':'contact'},{'id':'site_id'}]}]})

    def information(self):
        return {'context':[{'id':'project','label':'Project','value':'Recorded project'}],
            'fields':[{'id':'site_name','scope':'site','label':'Site name','type':'text','value':'Recorded site'},
                {'id':'contact','scope':'general','section_id':'general','label':'Contact','type':'text','value':'Engineer contact'},
                {'id':'site_id','scope':'general','section_id':'general','label':'Site ID','type':'text','system':'site_id','value':'SYNTHETIC'}]}

    def test_flat_rows_preserve_input_and_classify_system_source_and_qa_cells(self):
        from .qa_site_information import table
        info=self.information();before=deepcopy(info)
        items=[{'id':'contact','value':'QA contact','accepted':True,'status':'Reported'},
            {'id':'site_id','value':'SYNTHETIC','accepted':False,'status':'Reported'}]
        result=table(self.checklist(),info,items,can_review=True)
        self.assertEqual(len(result['rows']),4)
        fields={row['field_id']:row for row in result['rows'] if row['field_id']}
        self.assertEqual(fields['contact']['value'],'QA contact')
        self.assertEqual(fields['contact']['submitted_value'],'Engineer contact')
        self.assertFalse(fields['site_id']['can_edit']);self.assertTrue(fields['site_id']['can_confirm'])
        self.assertEqual(info,before)

    def test_finished_review_disables_every_cell_control(self):
        from .qa_site_information import table
        result=table(self.checklist(),self.information(),[{'id':'contact','value':'Reported'}],can_review=False)
        self.assertFalse(result['can_review'])
        self.assertFalse(any(row['can_edit'] or row['can_confirm'] for row in result['rows']))
