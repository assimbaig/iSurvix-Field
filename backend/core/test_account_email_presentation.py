"""Saved onboarding and all supported project-role invitations use one outbox."""
import hashlib,json,uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Company,IndustryCatalog,Profile,Project,ProjectInvitation,InvitationEmailDelivery
from .notification_email import GraphMailConfig
from .test_notification_email_transport import graph_fixture,TENANT,CLIENT,SECRET


@override_settings(NOTIFICATION_EMAIL_ENABLED=True,NOTIFICATION_EMAIL_PUBLIC_ORIGIN='https://testserver',
    ALLOWED_HOSTS=['testserver'],PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountInvitationPresentationTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_superuser('presentation-owner','owner@example.test','Fixture849!')
        self.industry=IndustryCatalog.objects.get(code='telecom')
        self.company=Company.objects.create(name='Synthetic Alpha & Partners')
        self.foreign=Company.objects.create(name='PRIVATE foreign company')
        self.admin=User.objects.create_user('presentation-admin','admin@example.test','Fixture849!')
        profile=self.admin.profile;profile.role=Profile.Roles.ADMIN;profile.company=self.company
        profile.admin_industry=self.industry;profile.save()
        self.project=Project.objects.create(name='Synthetic assigned project',company=self.company,administrator=self.admin)
        profile.project=self.project;profile.save()

    def delivery(self,role):
        from .invitation_email import prepare_invitation_token,queue_invitation_email
        token,identifier=prepare_invitation_token()
        invitation=ProjectInvitation.objects.create(project=self.project,company=self.company,
            email='invited-'+role.lower()+'@example.test',role=role,created_by=self.admin,
            expires_at=timezone.now()+timedelta(days=2),token_hash=hashlib.sha256(token.encode()).hexdigest())
        queue_invitation_email(invitation,identifier)
        return invitation,token

    def send(self):
        from .invitation_email import process_next_email
        with graph_fixture() as records,patch('core.notification_email.load_config',
                return_value=GraphMailConfig(TENANT,CLIENT,SECRET)):
            self.assertTrue(process_next_email());self.assertFalse(process_next_email())
        self.assertEqual(len(records),2)
        return json.loads(records[-1]['raw'])['message']

    def test_each_supported_project_role_receives_specific_saved_context_and_branding_once(self):
        for role in [Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT]:
            with self.subTest(role=role):
                invitation,token=self.delivery(role)
                message=self.send();body=message['body']['content']
                self.assertEqual(message['subject'],'Your iField project invitation')
                self.assertEqual(message['body']['contentType'],'HTML')
                self.assertIn('Synthetic Alpha &amp; Partners',body)
                self.assertIn(self.project.name,body)
                self.assertIn(invitation.get_role_display(),body)
                self.assertIn(token,body)
                self.assertIn('ifield-logo.webp',body)
                self.assertIn('please do not reply',body)
                self.assertNotIn(self.foreign.name,body)
                self.assertNotIn('Fixture849!',body)
                self.assertEqual(message['toRecipients'],[{'emailAddress':{'address':invitation.email}}])
                self.assertEqual(InvitationEmailDelivery.objects.get(invitation=invitation).status,'accepted')

    def test_company_onboarding_uses_admin_activation_copy_without_inventing_project(self):
        from .onboarding_service import apply_application,review_application,provision_application,invite_application
        app=apply_application(self.owner,request_key=uuid.uuid4(),name='Synthetic onboarding company',
            email='new-company-admin@example.test',industry=self.industry)
        review_application(self.owner,app.pk,approve=True);provision_application(self.owner,app.pk)
        app,token=invite_application(self.owner,app.pk)
        # Replay provisioning/invitation returns the existing saved records.
        replay,replayed=invite_application(self.owner,app.pk)
        self.assertEqual(replay.invitation_id,app.invitation_id)
        self.assertEqual(InvitationEmailDelivery.objects.count(),1)
        message=self.send();body=message['body']['content']
        self.assertEqual(message['subject'],'Activate your iField company administrator account')
        self.assertIn('Activate your company administrator account',body)
        self.assertIn('Synthetic onboarding company',body)
        self.assertNotIn('Project: Synthetic assigned project',body)
        self.assertIn(token,body)
