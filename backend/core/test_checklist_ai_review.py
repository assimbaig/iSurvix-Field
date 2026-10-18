"""Deterministic local critique validation and privacy regressions."""
import json
from contextlib import contextmanager
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Checklist,ChecklistTemplate,Project,Profile,ChecklistAIReview,GovernanceAudit
from .checklist_ai_review import snapshot,digest_snapshot,validate_findings,review_batches

@contextmanager
def lease():
    yield lambda:None

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,LOCAL_AI_ENABLED=True,OLLAMA_MODEL='fixture:local')
class ChecklistAIReviewTests(TestCase):
    def setUp(self):
        schema={'title':'Fixture','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        t=ChecklistTemplate.objects.create(name='Fixture',definition=schema,published=True)
        self.project=Project.objects.create(name='Review fixture',checklist_template=t)
        self.lead=self.person('lead',Profile.Roles.TEAM_LEAD)
        self.client_user=self.person('client-review',Profile.Roles.CLIENT)
        self.engineer=self.person('engineer-review',Profile.Roles.ENGINEER)
        self.c=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC',answer_data={'custom':{'condition':'Unknown'}})
        self.finding={'field_id':'condition','section_id':'general','severity':'high','uncertainty':'high','finding':'Visible evidence missing','missing_evidence':'Engineer inspection','sources':[]}
    def person(self,name,role):
        user=User.objects.create_user(name,password='fixture')
        user.profile.role=role
        user.profile.project=self.project
        user.profile.save()
        return user
    def url(self,name,*args):
        return reverse(name,args=[self.c.pk,*args])
    def review(self):
        return ChecklistAIReview.objects.create(checklist=self.c,requested_by=self.lead,model='fixture:local',snapshot_digest=digest_snapshot(snapshot(self.c)),status='completed',findings=[self.finding])
    def test_unknown_sources_and_field_ids_rejected(self):
        batch=list(review_batches(snapshot(self.c)))[0]
        for changes in [{'sources':[999]},{'field_id':'foreign'},{'section_id':'wrong'},{'severity':'pass'}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_findings({'findings':[{**self.finding,**changes}]},batch,set())
    def test_all_fields_batched_without_truncation(self):
        data=snapshot(self.c)
        data['schema']['sections'][0]['fields']=[{'id':f'f{i}','label':'x'*1000,'type':'text'} for i in range(40)]
        batches=list(review_batches(data))
        self.assertGreater(len(batches),1)
        self.assertEqual(sum(len(b) for b in batches),40)
    def test_engineer_own_review_visible_but_client_sharing_team_lead_only(self):
        self.client.force_login(self.engineer)
        response=self.client.get(self.url('checklist_ai_state'))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['can_request'])
        self.assertFalse(response.json()['can_share'])
        review=self.review()
        self.assertEqual(self.client.post(self.url('checklist_ai_share',review.pk),{'shared':'true','expected_digest':review.snapshot_digest}).status_code,403)
    def test_client_final_only_and_shared_current_only(self):
        r=self.review()
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).status_code,404)
        self.c.status=Checklist.Status.FINAL
        self.c.save()
        page=self.client.get(self.url('checklist_ai_review'))
        self.assertEqual(page.status_code,200)
        self.assertIn('no-store',page['Cache-Control'])
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).json()['reviews'],[])
        r.shared=True
        r.save()
        self.assertEqual(len(self.client.get(self.url('checklist_ai_state')).json()['reviews']),1)
        self.c.answer_data={'custom':{'condition':'Changed'}}
        self.c.save()
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).json()['reviews'],[])
    def test_explicit_share_audited_and_stale_share_refused(self):
        r=self.review()
        self.client.force_login(self.lead)
        target=self.url('checklist_ai_share',r.pk)
        self.assertEqual(self.client.post(target,{'shared':'true'}).status_code,409)
        self.assertEqual(self.client.post(target,{'shared':'true','expected_digest':r.snapshot_digest}).status_code,302)
        self.assertTrue(GovernanceAudit.objects.filter(project=self.project,action='checklist_ai_review_shared').exists())
        self.c.answer_data={'custom':{'condition':'New'}}
        self.c.save()
        self.assertEqual(self.client.post(target,{'shared':'true','expected_digest':r.snapshot_digest}).status_code,409)
        self.assertEqual(self.client.post(target,{'shared':'false','expected_digest':r.snapshot_digest}).status_code,302)
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_mocked_local_review_never_changes_answers_or_approvals(self,call,models):
        call.side_effect=[{'capabilities':['completion']},{'message':{'content':json.dumps({'findings':[self.finding]})}}]
        self.client.force_login(self.lead)
        response=self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        self.c.refresh_from_db()
        self.assertEqual(self.c.answer_data,{'custom':{'condition':'Unknown'}})
        self.assertEqual(self.c.section_approvals,{})
        self.assertEqual(self.c.status,Checklist.Status.DRAFT)
        self.assertFalse(self.c.ai_reviews.get().shared)
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_malformed_response_persisted_failed_and_private(self,call,models):
        call.side_effect=[{'capabilities':['completion']},{'message':{'content':'bad json'}}]
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json').status_code,503)
        self.assertEqual(self.c.ai_reviews.get().status,'failed')
        self.assertFalse(self.c.ai_reviews.get().shared)

    def test_csrf_and_foreign_project_denied(self):
        from django.test import Client
        secure=Client(enforce_csrf_checks=True)
        secure.force_login(self.lead)
        self.assertEqual(secure.post(self.url('checklist_ai_request')).status_code,403)
        other=Project.objects.create(name='Foreign review project')
        self.lead.profile.project=other
        self.lead.profile.save()
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.url('checklist_ai_request')).status_code,404)
    def test_client_cannot_share_or_request_even_final(self):
        self.c.status=Checklist.Status.FINAL
        self.c.save()
        r=self.review()
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.post(self.url('checklist_ai_request')).status_code,403)
        self.assertEqual(self.client.post(self.url('checklist_ai_share',r.pk),{'shared':'true','expected_digest':r.snapshot_digest}).status_code,403)
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=[])
    @patch('core.checklist_ai_review.ollama')
    def test_missing_model_fails_before_inference(self,call,models):
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.url('checklist_ai_request')).status_code,503)
        call.assert_not_called()
        self.assertFalse(self.c.ai_reviews.exists())
    def test_internal_review_never_enters_generic_export_or_chat_context(self):
        r=self.review()
        r.findings=[{**self.finding,'finding':'PRIVATE REVIEW SENTINEL'}]
        r.save()
        from .template_service import export_custom_excel
        import zipfile
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(export_custom_excel(self.c))) as archive:
            self.assertNotIn(b'PRIVATE REVIEW SENTINEL',b''.join(archive.read(n) for n in archive.namelist()))
        self.assertNotIn('PRIVATE REVIEW SENTINEL',json.dumps(self.c.answer_data))
        self.assertNotIn('PRIVATE REVIEW SENTINEL',json.dumps(self.c.review_history))
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_answer_change_during_inference_discards_results(self,call,models):
        def response(path,payload):
            if path=='/api/show':
                return {'capabilities':['completion']}
            Checklist.objects.filter(pk=self.c.pk).update(answer_data={'custom':{'condition':'Updated during inference'}})
            return {'message':{'content':json.dumps({'findings':[self.finding]})}}
        call.side_effect=response
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json').status_code,503)
        self.assertEqual(self.c.ai_reviews.get().status,'failed')
        self.assertEqual(self.c.ai_reviews.get().findings,[])
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_role_revoked_during_inference_rechecked_fresh(self,call,models):
        def response(path,payload):
            if path=='/api/show':
                return {'capabilities':['completion']}
            Profile.objects.filter(user=self.lead).update(role=Profile.Roles.ENGINEER)
            return {'message':{'content':json.dumps({'findings':[self.finding]})}}
        call.side_effect=response
        self.client.force_login(self.lead)
        self.assertEqual(self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json').status_code,403)
        self.assertEqual(self.c.ai_reviews.get().status,'failed')
    def test_review_batches_include_remarks_and_available_images(self):
        data=snapshot(self.c)
        data['remarks']={'condition':'Engineer remark'}
        data['images']={'condition':['private/source.png']}
        item=list(review_batches(data))[0][0]
        self.assertEqual(item['remarks'],'Engineer remark')
        self.assertEqual(item['existing_checklist_image_count'],1)
        self.assertNotIn('private/source.png',json.dumps(item))
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=[])
    def test_interrupted_private_review_recovered_on_next_request(self,models):
        r=self.review()
        r.status='running'
        r.save()
        self.client.force_login(self.lead)
        self.client.post(self.url('checklist_ai_request'))
        r.refresh_from_db()
        self.assertEqual(r.status,'failed')
        self.assertFalse(r.shared)

    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_assigned_engineer_can_request_final_checklist_review_but_cannot_share(self,call,models):
        self.c.status=Checklist.Status.FINAL
        self.c.save()
        call.side_effect=[{'capabilities':['completion']},{'message':{'content':json.dumps({'findings':[self.finding]})}}]
        self.client.force_login(self.engineer)
        response=self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        review=self.c.ai_reviews.get()
        self.assertFalse(review.shared)
        self.assertEqual(self.client.post(self.url('checklist_ai_share',review.pk),{'shared':'true','expected_digest':review.snapshot_digest}).status_code,403)
    def test_other_engineer_cannot_read_or_request_peer_checklist_review(self):
        peer=self.person('peer-review-engineer',Profile.Roles.ENGINEER)
        self.client.force_login(peer)
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).status_code,404)
        self.assertEqual(self.client.post(self.url('checklist_ai_request')).status_code,404)
    def test_photo_location_correction_invalidates_shared_critical_review(self):
        from .models import PhotoEvidence,PhotoPlacement
        self.c.status=Checklist.Status.FINAL
        self.c.save()
        photo=PhotoEvidence.objects.create(checklist=self.c,filename='synthetic.png',sha256='synthetic',group='Civil')
        review=self.review()
        review.shared=True
        review.save()
        self.client.force_login(self.client_user)
        self.assertEqual(len(self.client.get(self.url('checklist_ai_state')).json()['reviews']),1)
        PhotoPlacement.objects.create(photo=photo,field_id='condition',section_id='general',status='manual',schema_digest='fixture')
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).json()['reviews'],[])
    def test_engineer_does_not_read_team_lead_private_review(self):
        self.review()
        self.client.force_login(self.engineer)
        self.assertEqual(self.client.get(self.url('checklist_ai_state')).json()['reviews'],[])
    @patch('core.checklist_ai_review.ollama')
    def test_unprocessed_photo_blocks_final_review_before_any_native_call(self,call):
        from .models import PhotoEvidence
        PhotoEvidence.objects.create(checklist=self.c,filename='synthetic.png',sha256='synthetic')
        self.client.force_login(self.engineer)
        result=self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json')
        self.assertEqual(result.status_code,409)
        self.assertEqual(len(result.json()['analysis']['unprocessed_photo_ids']),1)
        call.assert_not_called()
        self.assertFalse(self.c.ai_reviews.exists())
    @patch('core.checklist_ai_review.inference_lease',lease)
    @patch('core.checklist_ai_review.installed_models',return_value=['fixture:local'])
    @patch('core.checklist_ai_review.ollama')
    def test_model_receives_corrected_photo_location_and_recommended_coverage(self,call,models):
        from .models import PhotoEvidence,PhotoPlacement,PhotoJob
        from .field_photo_service import schema_digest
        self.c.schema_snapshot['sections'][0]['fields'][0]['type']='inspection'
        self.c.save()
        photo=PhotoEvidence.objects.create(checklist=self.c,filename='synthetic.png',sha256='fixture-photo',group='Civil')
        PhotoPlacement.objects.create(photo=photo,field_id='condition',section_id='general',status='manual',schema_digest=schema_digest(self.c),reason='Engineer corrected mapping')
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.engineer,model='fixture:local',status='completed',schema=self.c.schema_snapshot,processed_photo_ids=[photo.pk])
        job.photos.add(photo)
        call.side_effect=[{'capabilities':['completion']},{'message':{'content':json.dumps({'findings':[self.finding]})}}]
        self.client.force_login(self.engineer)
        result=self.client.post(self.url('checklist_ai_request'),data='{}',content_type='application/json')
        self.assertEqual(result.status_code,201,result.content)
        payload=call.call_args_list[-1].args[1]
        item=json.loads(payload['messages'][1]['content'])['fields'][0]
        self.assertEqual(item['photo_locations'][0]['status'],'manual')
        self.assertEqual(item['photo_locations'][0]['photo_id'],photo.pk)
        self.assertEqual(item['evidence_coverage']['status'],'covered')
        self.assertFalse(item['evidence_coverage']['required'])
        self.assertEqual(item['photo_evidence'][0]['group'],'Civil')
