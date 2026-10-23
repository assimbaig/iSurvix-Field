"""Saved-data QA mapping regressions; ordinary tests use no native model."""
from copy import deepcopy
from types import SimpleNamespace

from django.test import TestCase, override_settings
from django.urls import reverse

from . import qa_matching, survey_processing as pipeline
from .models import ChecklistTemplate, WorkflowTemplateQualification
from .roadmap_service import definition_digest
from .survey_processing_models import SurveyProcessingResult, SurveySourceAnalysis
from . import test_engineer_category_submission_acceptance as capture_fixtures


@override_settings(SECRET_KEY='isolated-qa-matching-regressions',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class QAMatchingBackendTests(TestCase):
    person=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.person
    add_photo=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.add_photo
    post=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.post
    state=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.state
    raw=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.raw
    upload=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.upload
    submit=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.submit
    assert_submitted=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.assert_submitted
    qa_state=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_state
    qa_action=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.qa_action
    route=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.route
    complete_qa_manually=capture_fixtures.EngineerCategorySubmissionAcceptanceTests.complete_qa_manually

    def setUp(self):
        capture_fixtures.EngineerCategorySubmissionAcceptanceTests.setUp(self)
        self.schema['sections'][0]['group']='General Info'
        self.schema['sections'] += [
            {'id':'civil_test','title':'Civil test','group':'Civil','fields':[
                {'id':'civil_photo','label':'Civil source','type':'photo','instruction':'Inspect the complete footing'},
                {'id':'civil_note','label':'Civil record','type':'text'}]},
            {'id':'electric_test','title':'Electrical test','group':'Electrical','fields':[
                {'id':'electric_photo','label':'Electrical source','type':'photo'}]}]
        self.checklist.schema_snapshot=deepcopy(self.schema)
        self.checklist.save(update_fields=['schema_snapshot'])
        ChecklistTemplate.objects.filter(pk=self.template.pk).update(definition=self.schema)
        WorkflowTemplateQualification.objects.create(project=self.project,template=self.template,
            workflow_type=self.checklist.workflow_type,definition_digest=definition_digest(self.schema),
            criteria_reference='Synthetic expanded QA requirements',inspection_method='Read the actual synthetic source',
            reviewed_by=self.lead,reason='Explicit new qualification for this expanded fixture')
        first,_=self.upload('Civil')
        second,_=self.upload('Electrical',('synthetic-two',))
        third,_=self.upload('Tower',('synthetic-three',))
        self.ids=[first[0]['id'],second[0]['id'],third[0]['id']]
        response,_=self.submit()
        self.assertEqual(response.status_code,201,response.content)
        self.revision=self.assert_submitted()

    def mutate(self,action,**data):
        state=self.qa_state()
        return self.post('photo_capture_review_action',{'action':action,'revision_id':state['revision_id'],
            'source_digest':state['source_digest'],'expected_review_digest':state['review_digest'],
            'reason':'QA reviewed this source photo and selected its actual checklist point',**data})

    def test_confirm_unlink_reassign_preserve_other_links_without_accepting_work(self):
        source_snapshot=deepcopy(self.revision.snapshot)
        for field in ['civil_photo','electric_photo','manufacturer']:
            result=self.mutate('confirm_link',field_id=field,photo_id=self.ids[0])
            self.assertEqual(result.status_code,200,result.content)
        state=self.qa_state()
        self.assertEqual(state['counts']['assigned'],1)
        self.assertEqual(state['counts']['confirmed'],3)
        self.assertFalse(any(item['accepted'] for item in state['items']))
        self.assertEqual(state['unassigned_photo_ids'],self.ids[1:])
        removed=self.mutate('unlink',field_id='electric_photo',photo_id=self.ids[0])
        self.assertEqual(removed.status_code,200,removed.content)
        moved=self.mutate('reassign_link',from_field_id='civil_photo',to_field_id='electric_photo',photo_id=self.ids[0])
        self.assertEqual(moved.status_code,200,moved.content)
        state=self.qa_state()
        self.assertEqual({(x['photo_id'],x['field_id']) for x in state['links']},
            {(self.ids[0],'electric_photo'),(self.ids[0],'manufacturer')})
        self.assertEqual(state['photos'][0]['group'],'Civil')
        self.assertEqual(state['counts']['unassigned'],2)
        self.assertTrue(state['matching_history'])
        self.revision.refresh_from_db();self.checklist.refresh_from_db()
        self.assertEqual(self.revision.snapshot,source_snapshot)
        self.assertEqual(self.checklist.answer_data,{})

    def test_legacy_map_and_new_confirmation_never_accept_photo_item(self):
        result=self.mutate('map',field_id='civil_photo',photo_ids=[self.ids[0]])
        self.assertEqual(result.status_code,200,result.content)
        item=next(i for i in result.json()['items'] if i['id']=='civil_photo')
        self.assertFalse(item['accepted'])
        accepted=self.mutate('answer',field_id='civil_photo',value=None,photo_ids=[self.ids[0]])
        self.assertEqual(accepted.status_code,200,accepted.content)
        self.assertTrue(next(i for i in accepted.json()['items'] if i['id']=='civil_photo')['accepted'])

    def test_reordering_only_changes_personal_display_order(self):
        before=self.qa_state();snapshot=deepcopy(self.revision.snapshot)
        reordered=self.mutate('reorder',category='Civil',field_ids=['civil_note','civil_photo'],
            expected_order_digest=before['order_digest'])
        self.assertEqual(reordered.status_code,200,reordered.content)
        after=self.qa_state()
        self.assertEqual(after['display_order']['Civil'],['civil_note','civil_photo'])
        self.assertEqual(after['review_digest'],before['review_digest'])
        self.assertEqual(after['links'],before['links'])
        self.assertNotEqual(after['order_digest'],before['order_digest'])
        for ids in [['civil_photo','electric_photo'],['civil_photo','civil_photo'],['civil_photo']]:
            invalid=self.mutate('reorder',category='Civil',field_ids=ids,expected_order_digest=after['order_digest'])
            self.assertEqual(invalid.status_code,409,invalid.content)
        stale=self.mutate('reorder',category='Civil',field_ids=['civil_photo','civil_note'],
            expected_order_digest=before['order_digest'])
        self.assertEqual(stale.status_code,409,stale.content)
        self.revision.refresh_from_db();self.checklist.refresh_from_db()
        self.assertEqual(self.revision.snapshot,snapshot)
        self.assertEqual(self.checklist.schema_snapshot,self.schema)

    def test_old_page_cannot_edit_new_revision_with_identical_review_payload(self):
        old=self.qa_state()
        self.assertEqual(self.route(self.quality,'reject','Recheck the uploaded evidence').status_code,302)
        response,_=self.submit(actor=self.engineer)
        self.assertEqual(response.status_code,201,response.content)
        new=self.qa_state()
        self.assertEqual(new['review_digest'],old['review_digest'])
        self.assertNotEqual(new['revision_id'],old['revision_id'])
        for action in ['confirm_link','answer','retry','reorder']:
            result=self.post('photo_capture_review_action',{'action':action,
                'revision_id':old['revision_id'],'source_digest':old['source_digest'],
                'expected_review_digest':old['review_digest'],'field_id':'manufacturer','photo_id':self.ids[0],
                'value':'Stale overwrite','photo_ids':[self.ids[0]],'reason':'Stale page must not write',
                'category':'Civil','field_ids':['civil_note','civil_photo'],'expected_order_digest':old['order_digest']})
            self.assertEqual(result.status_code,409,result.content)
        current=self.checklist.processing_revisions.get(pk=new['revision_id'])
        self.assertFalse(current.processing_events.exclude(action='capture_submitted').exists())

    def test_unsupported_ai_sources_stay_unassigned_and_raw_observations_visible(self):
        findings=[{'source_id':'photo:'+str(self.ids[0]),'reference':'synthetic-one.png',
            'field_hint':'manufacturer','value':'SyntheticCo','confidence':'high','component':'cabinet',
            'evidence_quote':'SyntheticCo visible on the test label','basis':'recorded','unit':''}]
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        contact=next(i for i in payload['checklist_items'] if i['id']=='contact')
        contact.update(value=None,status='Missing',confidence='high',sources=[{'source_id':'photo:'+str(self.ids[1])}])
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        observed={'findings':findings,'reference':'synthetic-one.png'}
        SurveySourceAnalysis.objects.create(revision=self.revision,source_id='photo:'+str(self.ids[0]),
            payload=observed,digest=pipeline.digest(observed))
        state=self.qa_state()
        self.assertEqual([(link['photo_id'],link['field_id'],link['state']) for link in state['links']],
            [(self.ids[0],'manufacturer','ai_suggested')])
        self.assertIn(self.ids[1],state['unassigned_photo_ids'])
        self.assertEqual(state['photos'][0]['observations'][0]['evidence_quote'],findings[0]['evidence_quote'])
        for item in state['items']:
            if item['id']=='contact':self.assertEqual(item['sources'],[])

    def test_late_ai_cannot_restore_explicitly_removed_or_replace_confirmed_links(self):
        self.assertEqual(self.mutate('confirm_link',field_id='manufacturer',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.mutate('unlink',field_id='manufacturer',photo_id=self.ids[0]).status_code,200)
        self.assertEqual(self.mutate('confirm_link',field_id='electric_photo',photo_id=self.ids[1]).status_code,200)
        findings=[{'source_id':'photo:'+str(self.ids[0]),'field_hint':'manufacturer','value':'LateCo',
            'confidence':'high','basis':'recorded','unit':''}]
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        state=self.qa_state()
        self.assertEqual([(link['photo_id'],link['field_id']) for link in state['links']],[(self.ids[1],'electric_photo')])
        self.assertIn(self.ids[0],state['unassigned_photo_ids'])

    def test_locked_fields_and_invalid_targets_fail_atomically(self):
        self.checklist.section_approvals={'civil_test':{'by':self.lead.pk}}
        self.checklist.save(update_fields=['section_approvals'])
        before=self.revision.processing_events.count()
        for field,pid in [('civil_photo',self.ids[0]),('unknown',self.ids[0]),('manufacturer',self.photo.pk)]:
            result=self.mutate('confirm_link',field_id=field,photo_id=pid)
            self.assertEqual(result.status_code,409,result.content)
        self.assertEqual(self.revision.processing_events.count(),before)

    def test_genuinely_missing_template_and_schema_exposes_configuration_error_with_photos(self):
        self.assertEqual(self.route(self.quality,'reject','Template needs configuration').status_code,302)
        self.checklist.refresh_from_db()
        self.checklist.checklist_template=None;self.checklist.schema_snapshot={}
        self.checklist.save(update_fields=['checklist_template','schema_snapshot'])
        submitted,_=self.submit(actor=self.engineer)
        self.assertEqual(submitted.status_code,201,submitted.content)
        state=self.qa_state()
        self.assertTrue(state['config_error'])
        self.assertFalse(state['can_complete'])
        self.assertEqual(state['items'],[])
        self.assertEqual(len(state['photos']),3)
        self.assertEqual(state['counts']['unassigned'],3)
        self.assertEqual(self.mutate('confirm_link',field_id='manufacturer',photo_id=self.ids[0]).status_code,409)
        page=self.client.get(reverse('photo_workspace',args=[self.checklist.pk]))
        self.assertEqual(page.status_code,200,page.content)

    def test_actual_standard_categories_use_approved_metadata_and_explicit_fallback(self):
        from .template_service import default_definition
        definition=default_definition()
        fields=qa_matching.catalog(SimpleNamespace(snapshot={'schema':definition}))
        categories={section['id']:fields[section['fields'][0]['id']] for section in definition['sections']}
        for sid in ['grounding','utility','generator','hybrid','solar','transformer','disconnect','distribution','dc','operator_readings']:
            self.assertEqual(categories[sid]['category'],'Electrical',sid)
        self.assertEqual(categories['civil']['category'],'Civil')
        self.assertEqual(categories['inventory_stc']['category'],'Tower')
        for sid in ['shelter','video']:
            self.assertEqual(categories[sid]['category'],'')
            self.assertFalse(categories[sid]['category_known'])

    def test_a_high_finding_for_another_field_cannot_validate_low_or_unsupported_match(self):
        source='photo:'+str(self.ids[0])
        findings=[{'source_id':source,'field_hint':'manufacturer','value':'SyntheticCo','confidence':'high'},
                  {'source_id':source,'field_hint':'contact','value':'Uncertain contact','confidence':'low'}]
        item={'id':'contact','value':'Uncertain contact','status':'Needs review','confidence':'high',
              'sources':[{'source_id':source}],'conflict':False}
        self.assertEqual(qa_matching.valid_ai_sources(item,findings),[])
        item['id']='manufacturer';item['value']='SyntheticCo'
        self.assertEqual(len(qa_matching.valid_ai_sources(item,findings)),1)

    def test_original_and_crops_count_as_one_link_and_one_required_photo(self):
        from .category_intake import missing_for_review
        source='photo:'+str(self.ids[0])
        findings=[{'source_id':identifier,'field_hint':'manufacturer','value':'SyntheticCo','confidence':'high'}
                  for identifier in [source,source+':crop:1']]
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        state=self.qa_state()
        self.assertEqual(len(state['links']),1)
        self.assertEqual(state['counts']['assigned'],1)
        self.assertEqual(state['counts']['suggested'],1)
        # Two crop references remain traceable but cannot satisfy two-photo rules.
        self.checklist.schema_snapshot['sections'][0]['fields'][2]['evidence_rules']={'version':1,'min_photos':2}
        # Exercise the requirement evaluator with a matching approved definition;
        # the immutable submitted result and crop references remain untouched.
        self.checklist.checklist_template.definition=deepcopy(self.checklist.schema_snapshot)
        errors=missing_for_review(self.checklist)
        self.assertTrue(any('2 distinct source photos' in error for error in errors),errors)

    def test_shared_client_projection_excludes_optional_unaccepted_ai_values_and_links(self):
        job=self.revision.processing_job
        job.status='failed';job.error='PRIVATE_JOB_ERROR'
        job.save(update_fields=['status','error'])
        findings=[{'source_id':'photo:'+str(self.ids[1]),'reference':'synthetic-two.png',
            'field_hint':'civil_note','value':'PRIVATE_OPTIONAL_AI_GUESS','confidence':'high',
            'component':'label','evidence_quote':'PRIVATE_OPTIONAL_AI_QUOTE','basis':'recorded','unit':''}]
        payload=pipeline.prepare_checklist(self.revision.snapshot,{'findings':findings,'missing':[],'conflicts':[]})
        SurveyProcessingResult.objects.create(revision=self.revision,payload=payload,digest=pipeline.digest(payload))
        qa=self.qa_state()
        self.assertEqual(next(item for item in qa['items'] if item['id']=='civil_note')['value'],'PRIVATE_OPTIONAL_AI_GUESS')
        self.complete_qa_manually()
        self.assertEqual(self.route(self.quality,'approve').status_code,302)
        self.assertEqual(self.route(self.lead,'approve').status_code,302)
        self.client.force_login(self.customer)
        shared=self.client.get(reverse('photo_capture_review_state',args=[self.checklist.pk]))
        self.assertEqual(shared.status_code,200,shared.content)
        item=next(item for item in shared.json()['items'] if item['id']=='civil_note')
        self.assertFalse(item['accepted'])
        self.assertIsNone(item['value'])
        self.assertIsNone(item['proposed_answer'])
        self.assertEqual(item['sources'],[])
        self.assertNotIn(b'PRIVATE_OPTIONAL_AI',shared.content)
        self.assertNotIn(b'PRIVATE_JOB_ERROR',shared.content)
        human=next(item for item in shared.json()['items'] if item['id']=='manufacturer')
        self.assertEqual(human['value'],'SyntheticCo')
        self.assertTrue(human['sources'])
        self.assertEqual(len(shared.json()['photos']),3)
        capture=self.client.get(reverse('photo_capture_state',args=[self.checklist.pk]))
        self.assertEqual(capture.status_code,403,capture.content)
        self.assertNotIn(b'PRIVATE_JOB_ERROR',capture.content)

    def test_closed_workflow_label_remains_distinct_from_queued_background_analysis(self):
        self.complete_qa_manually()
        for actor in [self.quality,self.lead,self.customer]:
            self.assertEqual(self.route(actor,'approve').status_code,302)
        self.checklist.refresh_from_db()
        state=self.qa_state()
        self.assertEqual(state['workflow_label'],self.checklist.workflow_label)
        self.assertEqual(state['workflow_stage'],self.checklist.workflow_stage)
        self.assertEqual(state['workflow_status'],self.checklist.status)
        self.assertEqual(state['revision_number'],self.revision.number)
        self.assertEqual(self.checklist.review_route_record.stage,'closed')
        self.assertEqual(state['ai']['status'],'queued')
        self.assertFalse(state['can_review'])
