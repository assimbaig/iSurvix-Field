"""Independent Client-role security tests using synthetic accounts and evidence."""
import hashlib
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import Checklist, ChecklistTemplate, Profile, Project, ProjectInvitation, PhotoEvidence, PhotoJob, PhotoDraft, WorkAssignment, GovernanceAudit


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, LOCAL_AI_ENABLED=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ClientAccessTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory(prefix='client-qa-',dir=Path(__file__).resolve().parents[2]/'.local')
        self.addCleanup(self.media.cleanup)
        self.storage=override_settings(MEDIA_ROOT=self.media.name)
        self.storage.enable()
        self.addCleanup(self.storage.disable)
        schema={'title':'Synthetic client checklist','sections':[{'id':'general','title':'General','fields':[{'id':'condition','label':'Condition','type':'text'}]}]}
        self.template=ChecklistTemplate.objects.create(name='Synthetic client checklist',published=True,definition=schema)
        self.project=Project.objects.create(name='Client synthetic project',checklist_template=self.template)
        self.other_project=Project.objects.create(name='Foreign synthetic project',checklist_template=self.template)
        self.engineer=self.person('client_fixture_engineer',Profile.Roles.ENGINEER,self.project)
        self.client_user=self.person('client_fixture_reviewer',Profile.Roles.CLIENT,self.project)
        self.client_user.first_name='Synthetic'
        self.client_user.last_name='Reviewer'
        self.client_user.save()
        self.foreign_client=self.person('foreign_reviewer',Profile.Roles.CLIENT,self.other_project)
        self.super=self.person('client_fixture_super',Profile.Roles.SUPER_ADMIN,superuser=True)
        self.admin=self.person('client_fixture_admin',Profile.Roles.ADMIN,self.project)
        self.final=Checklist.objects.create(user=self.engineer,project=self.project,site_id='CLIENT-FINAL',status=Checklist.Status.FINAL,answer_data={'custom':{'condition':'Engineer approved evidence'}},section_approvals={'general':{'by':self.engineer.pk}})
        self.draft=Checklist.objects.create(user=self.engineer,project=self.project,site_id='CLIENT-PRIVATE-DRAFT')
        self.foreign=Checklist.objects.create(user=self.foreign_client,project=self.other_project,site_id='CLIENT-FOREIGN-FINAL',status=Checklist.Status.FINAL)
        self.photo=PhotoEvidence.objects.create(checklist=self.final,uploaded_by=self.engineer,filename='synthetic.png',sha256=hashlib.sha256(b'synthetic-source').hexdigest(),metadata={'format':'PNG'})
        self.photo.original.save('original.bin',ContentFile(b'synthetic-source'))
        self.photo.preview.save('preview.jpg',ContentFile(b'synthetic-preview'))
        self.job=PhotoJob.objects.create(checklist=self.final,requested_by=self.engineer,model='synthetic',schema=schema,status='failed')
        self.job.photos.add(self.photo)
        self.proposal=PhotoDraft.objects.create(job=self.job,photo=self.photo,field_id='condition',label='Condition',value='AI must not overwrite',reason='Synthetic observation',uncertainty='high')
        self.task=WorkAssignment.objects.create(project=self.project,assigned_by=self.admin,assigned_to=self.engineer,site_id=self.final.site_id,latitude=24,longitude=46,description='Synthetic task',checklist=self.final)
        self.client.force_login(self.client_user)

    def person(self,name,role,project=None,superuser=False):
        user=User.objects.create_user(name,email=name+'@example.test',password='Client-fixture-294!')
        user.is_superuser=superuser
        user.is_staff=superuser
        user.save()
        user.profile.role=role
        user.profile.project=project
        user.profile.save()
        return user

    def decision(self,survey=None,**changes):
        survey=survey or self.final
        data={'decision':'approved','reference':'Synthetic signed review','expected_updated_at':survey.updated_at.isoformat(),'expected_review_token':survey.client_review_token}
        data.update(changes)
        return data

    def test_workspace_shows_only_own_project_final_without_personnel_or_tasks(self):
        response=self.client.get(reverse('governance_home'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'CLIENT-FINAL')
        self.assertNotContains(response,'CLIENT-PRIVATE-DRAFT')
        self.assertNotContains(response,'CLIENT-FOREIGN-FINAL')
        self.assertTrue(response.context['is_client'])
        self.assertTrue(response.context['can_client_approve'])
        for collection in ['assignments','members','invitations']:
            self.assertEqual(list(response.context[collection]),[])
        self.assertFalse(response.context['can_assign'] or response.context['can_invite'])

    def test_nonfinal_and_foreign_survey_routes_are_inaccessible_even_if_client_owned(self):
        self.draft.user=self.client_user
        self.draft.save()
        for survey in [self.draft,self.foreign]:
            for name,args in [('custom_checklist',[survey.pk]),('custom_checklist_download',[survey.pk]),('photo_workspace',[survey.pk]),('photo_state',[survey.pk]),('photo_report',[survey.pk]),('checklist_detail',[survey.pk]),('checklist_data_api',[survey.pk])]:
                with self.subTest(name=name,survey=survey.pk):
                    self.assertEqual(self.client.get(reverse(name,args=args)).status_code,404)
        self.client.force_login(self.foreign_client)
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[self.final.pk])).status_code,404)

    def test_final_checklist_and_evidence_sources_readable_without_changes(self):
        for name,args in [('custom_checklist',[self.final.pk]),('custom_checklist_download',[self.final.pk]),('photo_workspace',[self.final.pk]),('photo_state',[self.final.pk]),('photo_report',[self.final.pk])]:
            response=self.client.get(reverse(name,args=args))
            self.assertEqual(response.status_code,200,(name,response.content[:200] if not response.streaming else 'stream'))
            response.close()
        response=self.client.get(reverse('photo_evidence',args=[self.final.pk,self.photo.pk,'original']))
        self.assertEqual(response.status_code,200)
        self.assertEqual(b''.join(response.streaming_content),b'synthetic-source')
        response.close()
        self.final.refresh_from_db()
        self.assertEqual(self.final.answer_data['custom']['condition'],'Engineer approved evidence')
        self.assertEqual(self.final.client_approval,{})
        self.assertEqual(self.proposal.status,'pending')

    def test_all_answer_photo_and_engineering_review_mutations_rejected(self):
        routes=[('custom_checklist_save',[self.final.pk]),('custom_checklist_submit',[self.final.pk]),('custom_checklist_review',[self.final.pk]),('custom_checklist_upload',[self.final.pk,'condition']),('custom_checklist_photo_delete',[self.final.pk,'condition',0]),('photo_upload',[self.final.pk]),('photo_enqueue',[self.final.pk]),('photo_retry',[self.final.pk,self.job.pk]),('photo_accept',[self.final.pk,self.proposal.pk]),('checklist_autosave_api',[self.final.pk]),('checklist_submit',[self.final.pk]),('checklist_upload_image',[self.final.pk]),('checklist_upload_zip',[self.final.pk])]
        for name,args in routes:
            with self.subTest(name=name):
                response=self.client.post(reverse(name,args=args),json.dumps({'answers':{'condition':'Client forged answer'},'action':'approve','photo_ids':[self.photo.pk]}),content_type='application/json')
                self.assertIn(response.status_code,(400,403,404,409,410))
        self.final.refresh_from_db()
        self.job.refresh_from_db()
        self.proposal.refresh_from_db()
        self.assertEqual(self.final.answer_data['custom']['condition'],'Engineer approved evidence')
        self.assertEqual(self.final.status,Checklist.Status.FINAL)
        self.assertEqual(self.job.status,'failed')
        self.assertEqual(self.proposal.status,'pending')
        self.assertEqual(self.final.review_history,[])

    def test_client_denied_administration_invitations_membership_tasks_and_maintenance(self):
        routes=[('governance_projects',[]),('governance_invite',[]),('governance_assign',[]),('governance_reset',[]),('governance_member',[self.engineer.pk]),('governance_revoke_invite',[0]),('work_edit',[self.task.pk]),('work_delete',[self.task.pk]),('update_work_status',[self.task.pk]),('complete_work',[self.task.pk]),('create_checklist_from_work',[self.task.pk])]
        for name,args in routes:
            with self.subTest(name=name):
                self.assertIn(self.client.post(reverse(name,args=args),{'action':'deactivate','role':'ADMIN'}).status_code,(400,403,404,409,410))
        self.assertEqual(self.client.get(reverse('checklist_templates')).status_code,403)
        self.assertEqual(self.client.get(reverse('governance_audit')).status_code,403)
        denied=self.client.post(reverse('assign_work'),{'site_id':'FORGED-CLIENT-TASK','latitude':'24','longitude':'46','engineer_id':self.engineer.pk,'project_id':self.project.pk})
        self.assertEqual(denied.status_code,403)
        self.assertFalse(WorkAssignment.objects.filter(site_id='FORGED-CLIENT-TASK').exists())
        self.engineer.refresh_from_db()
        self.assertTrue(self.engineer.is_active)
        self.assertEqual(WorkAssignment.objects.count(),1)

    def test_client_decision_identity_is_bound_to_authenticated_account(self):
        url=reverse('governance_client_approval',args=[self.final.pk])
        response=self.client.post(url,self.decision(approver_name='Forged Person',approver_email='forged@example.test',recorded_by=self.super.pk,authenticated_client=False))
        self.assertEqual(response.status_code,302)
        self.final.refresh_from_db()
        decision=self.final.client_approval
        self.assertEqual(decision['approver_email'],self.client_user.email)
        self.assertEqual(decision['approver_name'],self.client_user.get_full_name())
        self.assertEqual(decision['recorded_by'],self.client_user.pk)
        self.assertTrue(decision['authenticated_client'])
        self.assertNotIn('forged@example.test',str(self.final.review_history))
        self.assertEqual(self.final.status,Checklist.Status.FINAL)
        self.assertEqual(self.final.answer_data['custom']['condition'],'Engineer approved evidence')
        self.assertTrue(GovernanceAudit.objects.filter(actor=self.client_user,project=self.project).exists())
        self.assertEqual(self.client.post(url,self.decision()).status_code,302)

    def test_client_decision_requires_csrf_and_fresh_approved_evidence(self):
        url=reverse('governance_client_approval',args=[self.final.pk])
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.client_user)
        self.assertEqual(strict.post(url,self.decision()).status_code,403)
        payload=self.decision()
        Checklist.objects.filter(pk=self.final.pk).update(answer_data={'custom':{'condition':'Changed after viewed'}})
        self.assertEqual(self.client.post(url,payload).status_code,409)
        self.assertIn(self.client.post(reverse('governance_client_approval',args=[self.draft.pk]),self.decision(self.draft)).status_code,(403,404,409))
        self.assertIn(self.client.post(reverse('governance_client_approval',args=[self.foreign.pk]),self.decision(self.foreign)).status_code,(403,404))
        self.final.refresh_from_db()
        self.assertEqual(self.final.client_approval,{})

    def test_client_invitations_require_scoped_admin_and_super_is_denied(self):
        for actor in [self.admin]:
            self.client.force_login(actor)
            email=actor.username+'-newclient@example.test'
            response=self.client.post(reverse('governance_invite'),{'email':email,'role':Profile.Roles.CLIENT,'project':self.project.pk})
            self.assertEqual(response.status_code,200)
            invitation=ProjectInvitation.objects.get(email=email)
            self.assertEqual(invitation.role,Profile.Roles.CLIENT)
            self.assertEqual(invitation.project,self.project)
            path=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(response.context['invite_url']).path
            accepted=Client().post(path,{'username':actor.username+'_invited_client','email':email,'password1':'Invited-client-284!','password2':'Invited-client-284!'})
            self.assertEqual(accepted.status_code,302)
            user=User.objects.get(email=email)
            self.assertEqual(user.profile.role,Profile.Roles.CLIENT)
            self.assertFalse(user.is_staff or user.is_superuser)
        self.client.force_login(self.super)
        response=self.client.post(reverse('governance_invite'),{'email':'super-denied-client@example.test','role':Profile.Roles.CLIENT,'project':self.project.pk})
        self.assertIn(response.status_code,(400,403))
        self.assertFalse(ProjectInvitation.objects.filter(email='super-denied-client@example.test').exists())
        self.client.force_login(self.admin)
        self.assertIn(self.client.post(reverse('governance_invite'),{'email':'crossproject@example.test','role':Profile.Roles.CLIENT,'project':self.other_project.pk}).status_code,(400,403,404))

    def test_locked_client_loses_existing_session_access(self):
        self.client_user.profile.is_locked=True
        self.client_user.profile.save()
        self.assertIn(self.client.get(reverse('governance_home')).status_code,(403,404))
        self.assertEqual(self.client.get(reverse('custom_checklist',args=[self.final.pk])).status_code,404)
        self.assertIn(self.client.post(reverse('governance_client_approval',args=[self.final.pk]),self.decision()).status_code,(403,404))

    @patch('core.local_ai.ollama')
    def test_client_text_assistant_reads_only_own_final_without_tools_or_mutation(self,call):
        for survey in [self.draft,self.foreign]:
            response=self.client.post('/local-ai/chat/',json.dumps({'question':'Describe current evidence','checklist_id':survey.pk}),content_type='application/json')
            self.assertEqual(response.status_code,404)
        call.assert_not_called()
        call.side_effect=[{'models':[{'name':'qwen3.5:4b'}]},{'message':{'content':'Evidence summary only.'}}]
        response=self.client.post('/local-ai/chat/',json.dumps({'question':'Describe current evidence','checklist_id':self.final.pk}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['answer'],'Evidence summary only.')
        payload=call.call_args.args[1]
        self.assertIn('CLIENT-FINAL',payload['messages'][1]['content'])
        self.assertNotIn('CLIENT-PRIVATE-DRAFT',str(payload))
        self.assertNotIn('CLIENT-FOREIGN-FINAL',str(payload))
        self.assertNotIn('tools',payload)
        self.final.refresh_from_db()
        self.assertEqual(self.final.answer_data['custom']['condition'],'Engineer approved evidence')
        self.assertEqual(self.final.client_approval,{})
        self.assertEqual(self.final.review_history,[])
        page=self.client.get('/local/assistant/')
        self.assertContains(page,'CLIENT-FINAL')
        self.assertNotContains(page,'CLIENT-PRIVATE-DRAFT')
        self.assertNotContains(page,'CLIENT-FOREIGN-FINAL')
