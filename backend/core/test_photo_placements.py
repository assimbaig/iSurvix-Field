"""Photo placement/coverage acceptance tests with synthetic images only."""
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings,Client
from .models import Checklist,ChecklistTemplate,Project,Profile,PhotoEvidence,PhotoJob,PhotoPlacement,GovernanceAudit
from .field_photo_service import schema_digest,coverage,record_proposals,confirmed_placements

@contextmanager
def lease(*args, **kwargs):
    yield lambda:None

@override_settings(ROOT_URLCONF='checklist.urls_local',ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PhotoPlacementTests(TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'.local')
        self.addCleanup(temp.cleanup)
        storage=override_settings(MEDIA_ROOT=temp.name)
        storage.enable()
        self.addCleanup(storage.disable)
        self.schema={'title':'Synthetic evidence','sections':[{'id':'civil','title':'Civil','fields':[{'id':'civil_photo','label':'Site foundation photo','type':'photo','required':True},{'id':'condition','label':'Foundation condition','type':'inspection'}]},{'id':'tower','title':'Tower','fields':[{'id':'tower_photo','label':'Tower photo','type':'photo','required':True}]}]}
        t=ChecklistTemplate.objects.create(name='Synthetic evidence',definition=self.schema,published=True)
        self.project=Project.objects.create(name='Placement fixture',checklist_template=t)
        self.user=User.objects.create_user('placement_engineer')
        self.user.profile.project=self.project
        self.user.profile.role=Profile.Roles.ENGINEER
        self.user.profile.save()
        self.c=Checklist.objects.create(project=self.project,user=self.user,site_id='SYNTHETIC')
        self.client.force_login(self.user)
        self.base=f'/local/photos/{self.c.pk}/'
    def image(self):
        data=BytesIO()
        Image.new('RGB',(60,60),'green').save(data,format='PNG')
        return SimpleUploadedFile('synthetic.png',data.getvalue(),content_type='image/png')
    def upload(self,group='Civil'):
        result=self.client.post(self.base+'upload/',{'group':group,'files':[self.image()]})
        self.assertEqual(result.status_code,201,result.content)
        return PhotoEvidence.objects.get(pk=result.json()['photos'][0]['id'])
    def propose(self,photo=None,fid='civil_photo'):
        photo=photo or self.upload()
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema),baseline={},total=1)
        job.photos.add(photo)
        record_proposals(job,photo,[{'field_id':fid,'reason':'The visible concrete base corresponds to the requested foundation evidence.','visual_evidence':'A rectangular concrete foundation is visible beneath the upright structure.','evidence_match':'visible','uncertainty':'medium'}])
        return PhotoPlacement.objects.get(photo=photo,field_id=fid)
    def mapping(self,decisions,**kwargs):
        return self.client.post(self.base+'mapping/',json.dumps({'decisions':decisions,'expected_schema_digest':schema_digest(self.c),**kwargs}),content_type='application/json')
    def decision(self,p,action='confirm'):
        return {'photo_id':p.photo_id,'field_id':p.field_id,'mapping_id':p.pk,'action':action}
    def test_group_upload_deduplicates_preserves_original_and_hint(self):
        p=self.upload()
        with p.original.open('rb') as source:
            original=source.read()
        duplicate=self.upload('Tower')
        self.assertEqual(p.pk,duplicate.pk)
        self.assertEqual(duplicate.group,'Civil')
        with duplicate.original.open('rb') as source:
            self.assertEqual(source.read(),original)
        result=self.client.post(self.base+'upload/',{'group':'arbitrary','files':[self.image()]})
        self.assertEqual(result.status_code,409)
    def test_ai_only_location_uncertain_confirmed_location_covers_required_photo(self):
        p=self.propose()
        self.assertEqual(coverage(self.c)['uncertain_count'],1)
        self.assertEqual(coverage(self.c)['missing_count'],2)
        self.assertEqual(confirmed_placements(self.c),{})
        result=self.mapping([self.decision(p)])
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(coverage(self.c)['covered_count'],1)
        self.c.refresh_from_db()
        self.assertEqual(self.c.answer_data,{})
        self.assertEqual(self.c.image_data,{})
        self.assertEqual(self.c.section_approvals,{})
        self.assertTrue(GovernanceAudit.objects.filter(action='photo_mapping_confirm').exists())
    def test_correct_misleading_photo_reject_old_confirmed_and_assign_actual_location(self):
        p=self.propose()
        self.mapping([self.decision(p)])
        result=self.mapping([self.decision(p,'reject'),{'photo_id':p.photo_id,'field_id':'tower_photo','action':'manual'}])
        self.assertEqual(result.status_code,200,result.content)
        p.refresh_from_db()
        self.assertEqual(p.status,'rejected')
        self.assertEqual(PhotoPlacement.objects.get(photo=p.photo,field_id='tower_photo').status,'manual')
        self.assertEqual(coverage(self.c)['covered_count'],1)
        self.assertEqual(coverage(self.c)['missing_count'],2)
    def test_bulk_review_is_atomic_on_wrong_photo_or_field(self):
        p=self.propose()
        response=self.mapping([self.decision(p),{'photo_id':9999,'field_id':'tower_photo','action':'manual'}])
        self.assertEqual(response.status_code,409)
        p.refresh_from_db()
        self.assertEqual(p.status,'proposed')
        self.assertFalse(GovernanceAudit.objects.filter(action='photo_mapping_confirm').exists())
    def test_approved_field_locked_and_stale_schema_rejected(self):
        p=self.propose()
        self.c.section_approvals={'civil':{'by':self.user.pk}}
        self.c.save()
        self.assertEqual(self.mapping([self.decision(p)]).status_code,409)
        self.c.section_approvals={}
        self.c.save()
        self.assertEqual(self.mapping([self.decision(p)],expected_schema_digest='stale').status_code,409)
    def test_rejected_and_human_corrected_locations_survive_ai_rerun(self):
        p=self.propose()
        self.mapping([self.decision(p,'reject')])
        self.propose(p.photo)
        p.refresh_from_db()
        self.assertEqual(p.status,'rejected')
        self.assertEqual(self.mapping([{'photo_id':p.photo_id,'field_id':'tower_photo','action':'manual'}]).status_code,200)
        self.propose(p.photo,'tower_photo')
        self.assertEqual(PhotoPlacement.objects.get(photo=p.photo,field_id='tower_photo').status,'manual')
    def test_one_original_can_be_explicitly_linked_multiple_locations(self):
        p=self.upload()
        self.assertEqual(self.mapping([{'photo_id':p.pk,'field_id':fid,'action':'manual'} for fid in ['civil_photo','tower_photo']]).status_code,200)
        self.assertEqual(coverage(self.c)['covered_count'],2)
        self.assertEqual(PhotoEvidence.objects.count(),1)
    def test_mapping_csrf_foreign_project_and_final_protected(self):
        p=self.propose()
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.base+'mapping/',json.dumps({'decisions':[self.decision(p)]}),content_type='application/json').status_code,403)
        other=User.objects.create_user('other_engineer')
        other.profile.project=self.project
        other.profile.role=Profile.Roles.ENGINEER
        other.profile.save()
        self.client.force_login(other)
        self.assertEqual(self.mapping([self.decision(p)]).status_code,404)
        self.client.force_login(self.user)
        self.c.status=Checklist.Status.FINAL
        self.c.save()
        self.assertEqual(self.mapping([self.decision(p)]).status_code,409)
    @patch('core.photo_queue.inference_lease',lease)
    @patch('core.photo_service.analyze_photo')
    def test_durable_worker_creates_proposed_locations_without_answers(self,analyze):
        p=self.upload()
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema),baseline={},total=1)
        job.photos.add(p)
        analyze.return_value=[{'field_id':'civil_photo','value':None,'reason':'The visible concrete base corresponds to the requested foundation evidence.','visual_evidence':'A rectangular concrete foundation is visible beneath the upright structure.','evidence_match':'visible','uncertainty':'low','missing_information':'','anomalies':[]}]
        from .photo_queue import process_next
        self.assertTrue(process_next())
        location=PhotoPlacement.objects.get(photo=p)
        self.assertEqual(location.status,'proposed')
        self.assertEqual(location.confidence,'high')
        self.c.refresh_from_db()
        self.assertEqual(self.c.answer_data,{})
        job.refresh_from_db()
        self.assertEqual(job.status,'completed')

    def test_recommended_inspection_evidence_never_invents_mandatory_requirement(self):
        result=coverage(self.c)
        inspection=next(item for item in result['evidence_slots'] if item['field_id']=='condition')
        self.assertFalse(inspection['required'])
        self.assertEqual(inspection['requirement'],'Recommended evidence')
        self.assertEqual(inspection['status'],'missing')
        self.assertEqual(result['required_missing_count'],2)
        self.assertEqual(result['recommended_missing_count'],1)
        self.c.answer_data={'custom':{'condition':{'result':'Not applicable','remarks':'Engineer confirmed no foundation at this location'}}}
        self.c.save()
        result=coverage(self.c)
        self.assertEqual(result['not_applicable_count'],1)
        self.assertEqual(result['recommended_missing_count'],0)
        self.assertEqual(result['required_missing_count'],2)
    def test_manual_na_needs_reason_and_does_not_exclude_required_evidence(self):
        self.c.answer_data={'custom':{'condition':{'result':'Not applicable','remarks':''}}}
        self.c.save()
        self.assertEqual(coverage(self.c)['not_applicable_count'],0)
        self.c.schema_snapshot['sections'][0]['fields'][1]['photo_required']=True
        self.c.answer_data={'custom':{'condition':{'result':'Not applicable','remarks':'Reason supplied'}}}
        self.c.save()
        self.assertEqual(coverage(self.c)['not_applicable_count'],0)
        self.assertEqual(coverage(self.c)['required_missing_count'],3)

    def test_analysis_readiness_includes_zero_draft_processed_photos(self):
        from .field_photo_service import analysis_state
        photo=self.upload()
        self.assertFalse(analysis_state(self.c)['review_ready'])
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema),status='completed',processed_photo_ids=[photo.pk],total=1,completed=1)
        job.photos.add(photo)
        result=analysis_state(self.c)
        self.assertTrue(result['review_ready'])
        self.assertEqual(result['analyzed_photo_ids'],[photo.pk])
        self.assertEqual(result['pending_mapping_count'],0)
        self.assertEqual(coverage(self.c)['missing_count'],3)
        job.status='queued'
        job.save()
        self.assertFalse(analysis_state(self.c)['review_ready'])
    def test_old_schema_processing_does_not_make_new_catalog_ready(self):
        from .field_photo_service import analysis_state
        photo=self.upload()
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema={'sections':[]},status='completed',processed_photo_ids=[photo.pk],total=1,completed=1)
        job.photos.add(photo)
        self.assertEqual(analysis_state(self.c)['unprocessed_photo_ids'],[photo.pk])
    @patch('core.photo_views.verify_vision')
    @patch('core.evidence_pipeline.model_fingerprint',return_value='a'*64)
    @patch('core.evidence_pipeline.tool_fingerprint',return_value='b'*64)
    def test_opt_in_group_queue_survives_running_job_without_parallel_inference(self,tools,model,vision):
        first=self.upload()
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema),status='running',total=1)
        job.photos.add(first)
        second=PhotoEvidence.objects.create(checklist=self.c,uploaded_by=self.user,filename='electrical.png',sha256='different-photo',group='Electrical')
        target=self.base+'enqueue/'
        response=self.client.post(target,json.dumps({'photo_ids':[second.pk],'queue_when_busy':True}),content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        queued=PhotoJob.objects.get(pk=response.json()['id'])
        self.assertEqual(queued.status,'queued')
        self.assertEqual(job.status,'running')
        duplicate=self.client.post(target,json.dumps({'photo_ids':[second.pk],'queue_when_busy':True}),content_type='application/json')
        self.assertEqual(duplicate.status_code,409)
        third=PhotoEvidence.objects.create(checklist=self.c,uploaded_by=self.user,filename='tower.png',sha256='third-photo',group='Tower')
        legacy=self.client.post(target,json.dumps({'photo_ids':[third.pk]}),content_type='application/json')
        self.assertEqual(legacy.status_code,409)
    def test_null_or_insufficient_draft_cannot_become_a_location(self):
        photo=self.upload()
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema))
        base={'field_id':'civil_photo','value':None,'reason':'Further close-up evidence is needed to identify this subject.','uncertainty':'low','visual_evidence':'The image shows only a distant view of an unidentified structure.'}
        for changes in [{},{'evidence_match':'insufficient'},{'evidence_match':'absent'},{'evidence_match':'visible','reason':'visible evidence'},{'evidence_match':'visible','visual_evidence':'visible evidence'}]:
            with self.subTest(changes=changes):
                record_proposals(job,photo,[{**base,**changes}])
                self.assertFalse(PhotoPlacement.objects.exists())
    @patch('core.photo_service.verify_vision')
    @patch('core.photo_service.ollama')
    def test_metadata_absent_subject_is_filtered_and_matches_remain_unconfirmed(self,call,vision):
        from .photo_service import analyze_photo
        photo=self.upload()
        metadata={'caption':'A concrete foundation supports an upright structure; no tower is visible.','objects':['concrete foundation'],'visible_text':[],'issues':[],'uncertainties':['Surface detail needs a close view.']}
        call.return_value={'message':{'content':json.dumps(metadata)}}
        proposals=analyze_photo(photo,self.schema,'fixture')
        self.assertEqual({p['field_id'] for p in proposals},{'civil_photo','condition'})
        self.assertTrue(all(p['value'] is None and p['uncertainty']=='high' for p in proposals))
        job=PhotoJob.objects.create(checklist=self.c,requested_by=self.user,model='fixture',schema=deepcopy(self.schema))
        record_proposals(job,photo,proposals)
        self.assertEqual(set(PhotoPlacement.objects.values_list('field_id',flat=True)),{'civil_photo','condition'})
        self.assertFalse(PhotoPlacement.objects.exclude(status='proposed').exists())
        self.assertEqual(self.c.answer_data,{})
        call.assert_called_once()
