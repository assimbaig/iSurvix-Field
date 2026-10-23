"""Atomic Engineer bulk category changes over actual isolated saved evidence."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json

from django.core.files.base import ContentFile
from django.db import DatabaseError
from django.test import Client,TestCase,override_settings
from django.urls import reverse

from . import test_survey_processing as fixtures
from .models import Checklist,GovernanceAudit,PhotoEvidence,PhotoJob,Profile
from .survey_processing_models import SurveyProcessingJob


@override_settings(SECRET_KEY='isolated-engineer-bulk-categories',ROOT_URLCONF='checklist.urls_local',
    ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EngineerBulkCategoryTests(TestCase):
    person=fixtures.SurveyProcessingTests.person
    add_photo=fixtures.SurveyProcessingTests.add_photo

    def setUp(self):
        fixtures.SurveyProcessingTests.setUp(self)
        self.third=self.add_photo('purple')
        self.ids=[self.photo.pk,self.photo2.pk,self.third.pk]
        for photo,group in zip([self.photo,self.photo2,self.third],['Civil','Electrical','Tower']):
            photo.group=group;photo.save(update_fields=['group'])
        self.originals={photo.pk:Path(photo.original.path).read_bytes() for photo in [self.photo,self.photo2,self.third]}
        self.before_schema=deepcopy(self.checklist.schema_snapshot)
        self.client.force_login(self.engineer)

    def state(self):
        response=self.client.get(reverse('photo_capture_state',args=[self.checklist.pk]))
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def move(self,ids=None,group='Tower',digest=None,**extra):
        data={'photo_ids':ids if ids is not None else self.ids[:2],
              'group':group,'expected_digest':digest or self.state()['digest'],**extra}
        return self.client.post(reverse('photo_capture_category',args=[self.checklist.pk]),
            json.dumps(data),content_type='application/json')

    def groups(self):
        return dict(self.checklist.photo_evidence.values_list('pk','group'))

    def audits(self):
        return GovernanceAudit.objects.filter(action='capture_photo_category',project=self.project)

    def unchanged_originals(self):
        for photo in self.checklist.photo_evidence.all():
            self.assertEqual(Path(photo.original.path).read_bytes(),self.originals[photo.pk])
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.schema_snapshot,self.before_schema)
        self.assertEqual(PhotoJob.objects.count(),0)
        self.assertEqual(SurveyProcessingJob.objects.count(),0)

    def test_one_batch_moves_exact_selection_and_records_actor_project_and_from_to(self):
        before=self.state()
        result=self.move()
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(self.groups(),dict.fromkeys(self.ids,'Tower'))
        self.assertNotEqual(result.json()['digest'],before['digest'])
        self.assertEqual(result.json()['category_update'],{'photo_ids':self.ids[:2],
            'requested_count':2,'selected_count':2,'changed_count':2,'unchanged_count':0,
            'duplicate_count':0,'group':'Tower','no_op':False})
        event=self.audits().get()
        self.assertEqual(event.actor_id,self.engineer.pk)
        self.assertEqual(event.project_id,self.project.pk)
        self.assertEqual(event.details['checklist_id'],self.checklist.pk)
        self.assertEqual(event.details['photo_ids'],self.ids[:2])
        self.assertEqual(event.details['changes'],[
            {'photo_id':self.ids[0],'from_group':'Civil','to_group':'Tower'},
            {'photo_id':self.ids[1],'from_group':'Electrical','to_group':'Tower'}])
        self.assertEqual({p['id']:p['group'] for p in self.state()['photos']},self.groups())
        self.unchanged_originals()

    def test_duplicate_ids_normalize_once_and_fresh_noop_does_not_duplicate_audit(self):
        result=self.move([self.ids[0],self.ids[0],self.ids[1]],'Electrical')
        self.assertEqual(result.status_code,200,result.content)
        details=result.json()['category_update']
        self.assertEqual((details['requested_count'],details['selected_count'],details['duplicate_count']),(3,2,1))
        self.assertEqual((details['changed_count'],details['unchanged_count']),(1,1))
        self.assertEqual(self.audits().count(),1)
        digest=result.json()['digest']
        repeated=self.move([self.ids[0],self.ids[0],self.ids[1]],'Electrical',digest)
        self.assertEqual(repeated.status_code,200,repeated.content)
        self.assertTrue(repeated.json()['category_update']['no_op'])
        self.assertEqual(repeated.json()['category_update']['changed_count'],0)
        self.assertEqual(repeated.json()['digest'],digest)
        self.assertEqual(self.audits().count(),1)
        self.unchanged_originals()

    def test_singleton_shape_remains_supported_with_photo_categories(self):
        response=self.client.post(reverse('photo_capture_category',args=[self.checklist.pk]),
            json.dumps({'photo_id':self.photo.pk,'group':'Electrical','expected_digest':self.state()['digest']}),
            content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.groups()[self.photo.pk],'Electrical')
        self.assertEqual(response.json()['category_update']['selected_count'],1)
        self.assertEqual(self.audits().get().details['photo_id'],self.photo.pk)

    def test_malformed_empty_nonpositive_ambiguous_or_unbounded_selection_is_rejected(self):
        before=self.groups()
        for ids in [[],None,'photos',{},[True],[1.0],[0],[-1],[str(self.photo.pk)],[None],[self.photo.pk]*1001]:
            with self.subTest(ids=repr(ids)[:80]):
                response=self.client.post(reverse('photo_capture_category',args=[self.checklist.pk]),
                    json.dumps({'photo_ids':ids,'group':'Tower','expected_digest':self.state()['digest']}),
                    content_type='application/json')
                self.assertEqual(response.status_code,409,response.content)
                self.assertEqual(self.groups(),before)
        ambiguous=self.move(photo_id=self.photo.pk)
        self.assertEqual(ambiguous.status_code,409,ambiguous.content)
        for group in ['Unknown',None,[],{}]:
            invalid=self.move(group=group)
            self.assertEqual(invalid.status_code,409,invalid.content)
        self.assertEqual(self.audits().count(),0)

    def test_foreign_missing_or_excluded_id_rejects_whole_batch_without_partial_change(self):
        other=Checklist.objects.create(project=self.project,user=self.engineer,site_id='SYNTHETIC-FOREIGN-BULK')
        foreign=PhotoEvidence.objects.create(checklist=other,uploaded_by=self.engineer,
            filename='foreign.png',sha256=self.photo.sha256)
        foreign.original.save('foreign.png',ContentFile(self.originals[self.photo.pk]))
        before=self.groups()
        for invalid in [foreign.pk,999999]:
            response=self.move([self.photo.pk,invalid])
            self.assertEqual(response.status_code,404,response.content)
            self.assertEqual(self.groups(),before)
        removed=self.client.post(reverse('photo_capture_remove',args=[self.checklist.pk]),
            json.dumps({'photo_id':self.third.pk,'expected_digest':self.state()['digest']}),content_type='application/json')
        self.assertEqual(removed.status_code,200,removed.content)
        excluded=self.move([self.photo.pk,self.third.pk])
        self.assertEqual(excluded.status_code,409,excluded.content)
        self.assertEqual(self.groups(),before)
        self.assertEqual(self.audits().count(),0)
        self.unchanged_originals()

    def test_stale_digest_rejects_all_selected_moves(self):
        old=self.state()['digest']
        self.assertEqual(self.move([self.third.pk],'Civil',old).status_code,200)
        before=self.groups()
        stale=self.move(self.ids[:2],'Tower',old)
        self.assertEqual(stale.status_code,409,stale.content)
        self.assertEqual(self.groups(),before)
        self.assertEqual(self.audits().count(),1)

    def test_wrong_roles_peer_owner_and_csrf_cannot_batch_move(self):
        before=self.groups();digest=self.state()['digest']
        peer=self.person('bulk_peer_engineer',Profile.Roles.ENGINEER)
        for actor in [self.admin,self.lead,self.quality,self.customer,peer]:
            self.client.force_login(actor)
            denied=self.move(digest=digest)
            self.assertIn(denied.status_code,(403,404),denied.content)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.engineer)
        denied=strict.post(reverse('photo_capture_category',args=[self.checklist.pk]),
            json.dumps({'photo_ids':self.ids[:2],'group':'Tower','expected_digest':digest}),content_type='application/json')
        self.assertEqual(denied.status_code,403)
        self.assertEqual(self.groups(),before)
        self.assertEqual(self.audits().count(),0)

    def test_submitted_and_final_work_preserve_frozen_groups_and_block_moves(self):
        submitted=self.client.post(reverse('photo_capture_submit',args=[self.checklist.pk]),
            json.dumps({'uploads_finished':True,'expected_digest':self.state()['digest']}),content_type='application/json')
        self.assertEqual(submitted.status_code,201,submitted.content)
        revision=self.checklist.processing_revisions.get();snapshot=deepcopy(revision.snapshot)
        for status in [Checklist.Status.SUBMITTED,Checklist.Status.FINAL]:
            Checklist.objects.filter(pk=self.checklist.pk).update(status=status)
            denied=self.move()
            self.assertEqual(denied.status_code,403,denied.content)
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot,snapshot)
        self.assertEqual(self.groups(),dict(zip(self.ids,['Civil','Electrical','Tower'])))
        self.assertEqual(self.audits().count(),0)

    def test_database_audit_failure_rolls_back_real_group_updates_atomically(self):
        before=self.groups();digest=self.state()['digest']
        def fail_after_write(*args,**kwargs):
            self.assertEqual(self.groups(),dict.fromkeys(self.ids,'Tower'))
            raise DatabaseError('Synthetic database audit write failure')
        with patch('core.governance_views.audit',side_effect=fail_after_write):
            result=self.move(digest=digest)
        self.assertEqual(result.status_code,409,result.content)
        self.assertEqual(self.groups(),before)
        self.assertEqual(self.state()['digest'],digest)
        self.assertEqual(self.audits().count(),0)
        self.unchanged_originals()
