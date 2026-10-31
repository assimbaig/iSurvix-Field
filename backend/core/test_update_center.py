"""Update Center tests use disposable catalogs/records and signed host receipts."""
from io import StringIO
from pathlib import Path
import hashlib,json,tempfile,uuid
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management import call_command
from django.test import Client,TestCase,override_settings
from django.urls import reverse
from .models import Profile


@override_settings(SECRET_KEY='isolated-update-signing-secret-not-a-deployment-key',ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'],SECURE_SSL_REDIRECT=False,ISURVIX_RELEASE_ID='a'*40,ISURVIX_EDITION='customer')
class UpdateCenterTests(TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2]/'.local'/'update-tests';root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.catalog=self.root/'catalog.json';self.receipts=self.root/'receipts';self.receipts.mkdir()
        self.entry={'release_id':'b'*40,'manifest_sha256':'c'*64,'supported_from':['a'*40],'editions':['customer','cloud']}
        self.catalog.write_text(json.dumps({'format':'isurvix-update-catalog-v1','releases':[self.entry]}))
        self.config=override_settings(ISURVIX_UPDATE_CATALOG_FILE=str(self.catalog),ISURVIX_UPDATE_RECEIPTS_ROOT=str(self.receipts))
        self.config.enable();self.addCleanup(self.config.disable)
        self.owner=User.objects.create_superuser('update-owner','owner@example.test','isolated-password')
        self.client.force_login(self.owner)

    def create(self,**changes):
        from .update_service import request_update
        data={'target_release':'b'*40,'expected_current':'a'*40,'request_key':str(uuid.uuid4()),'maintenance_confirmed':True}
        data.update(changes)
        return request_update(self.owner,**data)

    def receipt(self,request,sequence,status,**changes):
        from .update_service import sign_payload
        payload={'format':'isurvix-update-receipt-v1','request_id':str(request.pk),'source_release':request.source_release,
            'target_release':request.target_release,'manifest_sha256':request.manifest_sha256,'catalog_sha256':request.catalog_sha256,
            'edition':request.edition,'nonce':request.nonce,'sequence':sequence,'status':status,
            'release_id':request.target_release if status=='completed' else request.source_release,'error_code':'','at':1234567890}
        payload.update(changes)
        return {'payload':payload,'signature':sign_payload('receipt-v1',payload)}

    def save_receipt(self,request,sequence,status,**changes):
        directory=self.receipts/str(request.pk);directory.mkdir(exist_ok=True)
        path=directory/f'{sequence:06}.json';path.write_text(json.dumps(self.receipt(request,sequence,status,**changes)))
        return path

    def test_owner_saved_request_is_pending_idempotent_and_survives_refresh(self):
        from .update_models import ServerUpdateRequest
        from .update_service import request_update
        key=str(uuid.uuid4());first=self.create(request_key=key)
        replay=request_update(self.owner,target_release='b'*40,expected_current='a'*40,request_key=key,maintenance_confirmed=True)
        self.assertEqual(first.pk,replay.pk)
        self.assertEqual(ServerUpdateRequest.objects.count(),1)
        response=self.client.get(reverse('update_center'))
        self.assertContains(response,str(first.pk));self.assertContains(response,'Awaiting operator')
        first.refresh_from_db();self.assertEqual(first.status,'pending')

    def test_no_catalog_no_working_update_action_or_silent_success(self):
        self.catalog.unlink()
        response=self.client.get(reverse('update_center'))
        self.assertContains(response,'catalog')
        self.assertNotContains(response,'name="target_release"')
        with self.assertRaises(ValidationError):self.create()

    def test_anonymous_and_every_nonowner_role_are_denied(self):
        self.client.logout();self.assertEqual(self.client.get(reverse('update_center')).status_code,302)
        for role in (Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.CLIENT):
            user=User.objects.create_user('updates-'+role.lower())
            user.profile.role=role;user.profile.save()
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('update_center')).status_code,403)
            with self.assertRaises(PermissionDenied):
                from .update_service import request_update
                request_update(user,target_release='b'*40,expected_current='a'*40,request_key=str(uuid.uuid4()),maintenance_confirmed=True)

    def test_stale_version_unconfirmed_unknown_target_and_duplicate_active_are_rejected(self):
        for changes in ({'expected_current':'d'*40},{'maintenance_confirmed':False},{'target_release':'d'*40}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):self.create(**changes)
        self.create()
        with self.assertRaisesMessage(ValidationError,'active'):self.create()

    def test_csrf_and_unknown_execution_fields_are_rejected(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('update_request'),{}).status_code,403)
        self.assertEqual(self.client.post(reverse('update_request'),{'command':'rm -rf /'}).status_code,400)

    def test_export_is_current_authority_checked_signed_and_does_not_claim_install(self):
        from .update_service import export_request,sign_payload
        request=self.create();signed=export_request(request.pk)
        self.assertEqual(signed['signature'],sign_payload('request-v1',signed['payload']))
        self.assertGreater(signed['payload']['expires_at'],signed['payload']['issued_at'])
        request.refresh_from_db();self.assertEqual(request.status,'pending')
        self.owner.is_active=False;self.owner.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):export_request(request.pk)

    def test_management_export_uses_existing_application_not_a_host_django_install(self):
        request=self.create();output=StringIO()
        call_command('update_bridge','export',str(request.pk),stdout=output)
        signed=json.loads(output.getvalue());self.assertEqual(signed['payload']['request_id'],str(request.pk))

    def test_sequenced_receipts_persist_once_and_completion_requires_target_running(self):
        from .update_service import reconcile_receipts
        request=self.create()
        self.save_receipt(request,1,'verified');self.save_receipt(request,2,'applying')
        reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertEqual((request.status,request.last_sequence),('applying',2))
        self.save_receipt(request,3,'completed')
        with self.assertRaises(ValidationError):reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertEqual(request.status,'applying')
        with override_settings(ISURVIX_RELEASE_ID='b'*40):
            reconcile_receipts(self.owner,request.pk);reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertEqual(request.status,'completed')
        self.assertEqual(request.events.count(),4)  # creation plus three actual host phases

    def test_tampered_or_foreign_receipt_cannot_report_false_success(self):
        from .update_service import reconcile_receipts
        request=self.create();path=self.save_receipt(request,1,'verified')
        data=json.loads(path.read_text());data['payload']['target_release']='d'*40;path.write_text(json.dumps(data))
        with self.assertRaises(ValidationError):reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertEqual(request.status,'pending')
        self.assertEqual(request.last_sequence,0)

    def test_receipt_gap_and_unknown_error_detail_are_rejected(self):
        from .update_service import reconcile_receipts
        request=self.create();self.save_receipt(request,2,'applying')
        with self.assertRaises(ValidationError):reconcile_receipts(self.owner,request.pk)
        (self.receipts/str(request.pk)/'000002.json').unlink()
        self.save_receipt(request,1,'failed',error_code='secret-server-stack-trace')
        with self.assertRaises(ValidationError):reconcile_receipts(self.owner,request.pk)

    def test_catalog_changes_after_request_do_not_silently_change_the_target(self):
        from .update_service import export_request
        request=self.create();catalog=json.loads(self.catalog.read_text());catalog['releases'][0]['manifest_sha256']='d'*64
        self.catalog.write_text(json.dumps(catalog))
        with self.assertRaises(ValidationError):export_request(request.pk)
        request.refresh_from_db();self.assertEqual(request.manifest_sha256,'c'*64)

    def test_untrusted_catalog_shapes_and_private_path_fields_are_rejected(self):
        from .update_service import catalog
        for change in ({'manifest_sha256':''},{'package_path':'/private/package'},{'release_record_sha256':'not-a-hash'},{'supported_from':[]},{'editions':['unknown']}):
            data={'format':'isurvix-update-catalog-v1','releases':[{**self.entry,**change}]}
            self.catalog.write_text(json.dumps(data))
            with self.subTest(change=change),self.assertRaises(ValidationError):catalog()
        self.catalog.write_text('{"format":"wrong","format":"isurvix-update-catalog-v1","releases":[]}')
        with self.assertRaises(ValidationError):catalog()

    def test_idempotency_key_cannot_rebind_to_different_update_inputs(self):
        key=str(uuid.uuid4());saved=self.create(request_key=key)
        with self.assertRaises(ValidationError):self.create(request_key=key,target_release='d'*40)
        saved.refresh_from_db();self.assertEqual(saved.target_release,'b'*40)

    def test_changed_receipt_at_existing_sequence_is_not_silently_replaced(self):
        from .update_service import reconcile_receipts
        request=self.create();self.save_receipt(request,1,'verified')
        reconcile_receipts(self.owner,request.pk)
        self.save_receipt(request,1,'verified',at=1234567891)
        with self.assertRaises(ValidationError):reconcile_receipts(self.owner,request.pk)
        self.assertEqual(request.events.get(sequence=1).details['at'],1234567890)

    def test_receipt_for_other_request_cannot_change_state(self):
        from .update_service import sign_payload,apply_receipt
        request=self.create();signed=self.receipt(request,1,'verified')
        signed['payload']['nonce']='d'*32;signed['signature']=sign_payload('receipt-v1',signed['payload'])
        with self.assertRaisesMessage(ValidationError,'different update'):apply_receipt(signed,actor=self.owner)
        request.refresh_from_db();self.assertEqual(request.status,'pending')

    def test_uncertain_activation_blocks_another_update_until_verified_recovery(self):
        from .update_service import reconcile_receipts
        request=self.create();self.save_receipt(request,1,'verified');self.save_receipt(request,2,'applying')
        self.save_receipt(request,3,'failed',error_code='activation_uncertain',release_id=request.target_release)
        reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertTrue(request.active)
        with self.assertRaisesMessage(ValidationError,'active'):self.create()
        self.save_receipt(request,4,'rolled_back')
        reconcile_receipts(self.owner,request.pk)
        request.refresh_from_db();self.assertEqual(request.status,'rolled_back');self.assertFalse(request.active)

    def test_event_history_is_immutable_and_raw_private_errors_cannot_be_signed_into_ui(self):
        from .update_service import apply_receipt,sign_payload
        request=self.create()
        with self.assertRaises(ValidationError):request.events.update(status='completed')
        signed=self.receipt(request,1,'failed',error_code='operation_failed')
        signed['payload']['message']='PRIVATE-KEY-OR-TRACE';signed['signature']=sign_payload('receipt-v1',signed['payload'])
        with self.assertRaises(ValidationError):apply_receipt(signed,actor=self.owner)
        response=self.client.get(reverse('update_center'))
        self.assertNotContains(response,'PRIVATE-KEY-OR-TRACE')

    def test_correct_signature_with_invalid_state_type_is_safe_validation_error(self):
        from .update_service import apply_receipt
        request=self.create();signed=self.receipt(request,1,[])
        with self.assertRaises(ValidationError):apply_receipt(signed,actor=self.owner)

    def test_owner_can_withdraw_pending_request_idempotently(self):
        from .update_service import withdraw_request
        request=self.create();withdraw_request(self.owner,request.pk);withdraw_request(self.owner,request.pk)
        request.refresh_from_db()
        self.assertEqual((request.status,request.error_code,request.active),('failed','cancelled',False))
        self.assertEqual(request.events.count(),2)
        self.assertEqual(request.last_sequence,1)
        self.assertNotEqual(self.create().pk,request.pk)

    def test_current_owner_can_withdraw_stuck_pending_after_requester_revocation(self):
        from .update_service import withdraw_request
        request=self.create();self.owner.is_active=False;self.owner.save(update_fields=['is_active'])
        replacement=User.objects.create_superuser('replacement-update-owner','new-owner@example.test','isolated')
        withdraw_request(replacement,request.pk)
        request.refresh_from_db();self.assertEqual(request.error_code,'cancelled')

    def test_withdrawal_is_forbidden_after_verified_receipt_and_cannot_bypass_ack(self):
        from .update_service import withdraw_request,reconcile_receipts,apply_receipt
        request=self.create();self.save_receipt(request,1,'verified');reconcile_receipts(self.owner,request.pk)
        with self.assertRaises(ValidationError):withdraw_request(self.owner,request.pk)
        # A separate pending request can be cancelled before the host's ACK;
        # the old verified receipt must then fail rather than authorise a stop.
        self.save_receipt(request,2,'failed',error_code='package_invalid');reconcile_receipts(self.owner,request.pk)
        pending=self.create();receipt=self.receipt(pending,1,'verified')
        withdraw_request(self.owner,pending.pk)
        with self.assertRaises(ValidationError):apply_receipt(receipt)

    def test_withdraw_route_requires_owner_csrf_and_pending_record(self):
        request=self.create();url=reverse('update_withdraw',args=[request.pk])
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(url).status_code,403)
        self.assertRedirects(self.client.post(url),reverse('update_center'))
        request.refresh_from_db();self.assertEqual(request.error_code,'cancelled')
