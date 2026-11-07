"""Isolated background export behavior; no operational data or model/network use."""
from io import BytesIO
from datetime import timedelta
import tempfile,uuid
from pathlib import Path
from django.test import TestCase,override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from openpyxl import load_workbook
from .models import Company,Project,Profile,WorkAssignment
from .export_service import request_export,process_next,safe_cell,download_authorized
from .export_models import DataExportJob

@override_settings(ROOT_URLCONF='checklist.urls_local',SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'],PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DataExportTests(TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.cfg=override_settings(DATA_EXPORT_ROOT=self.tmp.name);self.cfg.enable();self.addCleanup(self.cfg.disable)
  self.company=Company.objects.create(name='Export A');self.other=Company.objects.create(name='Export B')
  self.project=Project.objects.create(name='Export scope',company=self.company)
  self.foreign=Project.objects.create(name='Forbidden scope',company=self.other)
  self.engineer=self.person('eng',self.company,self.project)
  self.stranger=self.person('foreign',self.other,self.foreign)
  self.task=WorkAssignment.objects.create(site_id='=HYPERLINK("https://example.invalid")',latitude=1,longitude=2,description='Assigned task',assigned_to=self.engineer,assigned_by=self.engineer,project=self.project)
  WorkAssignment.objects.create(site_id='FOREIGN',latitude=1,longitude=2,description='secret',assigned_to=self.stranger,assigned_by=self.stranger,project=self.foreign)
 def person(self,name,company,project):
  u=User.objects.create_user(name,password='test-only-password');p=u.profile;p.role=Profile.Roles.ENGINEER;p.company=company;p.project=project;p.save();return u
 def export(self):return request_export(self.engineer,'tasks',request_key=str(uuid.uuid4()))[0]
 def test_queued_then_worker_builds_only_accessible_records_and_safe_cells(self):
  job=self.export();self.assertEqual(job.status,'queued');self.assertFalse(job.file_name)
  self.assertTrue(process_next());job.refresh_from_db();self.assertEqual(job.status,'ready',job.error)
  path=download_authorized(self.engineer,job)
  book=load_workbook(path,read_only=True,data_only=False)
  rows=list(book['Data'].values);self.assertEqual(len(rows),2);self.assertTrue(any(str(v).startswith("'=HYPERLINK") for v in rows[1]))
  self.assertNotIn('FOREIGN',str(rows));self.assertEqual(set(book.sheetnames),{'Data','Columns','Export'})
  self.assertEqual(job.row_count,1);self.assertRegex(job.file_name,r'^\d{4}_\d{2}_\d{2}_\d{6}_tasks\.xlsx$');book.close()
 def test_replayed_request_is_same_job_not_duplicate(self):
  key=str(uuid.uuid4());a,new=request_export(self.engineer,'tasks',request_key=key);b,new2=request_export(self.engineer,'tasks',request_key=key)
  self.assertTrue(new);self.assertFalse(new2);self.assertEqual(a.pk,b.pk)
  with self.assertRaises(ValidationError):request_export(self.engineer,'projects',request_key=key)
 def test_foreign_actor_and_revoked_scope_cannot_download(self):
  job=self.export();process_next();job.refresh_from_db()
  with self.assertRaises(PermissionDenied):download_authorized(self.stranger,job)
  p=self.engineer.profile;p.project=None;p.save()
  with self.assertRaises(PermissionDenied):download_authorized(self.engineer,job)
 def test_source_changes_deny_stale_artifact(self):
  job=self.export();process_next();job.refresh_from_db();self.task.description='Changed';self.task.save()
  with self.assertRaises(PermissionDenied):download_authorized(self.engineer,job)
 def test_expired_and_tampered_artifacts_are_unavailable(self):
  job=self.export();process_next();job.refresh_from_db();path=download_authorized(self.engineer,job);Path(path).write_bytes(b'corrupt')
  with self.assertRaises(ValidationError):download_authorized(self.engineer,job)
  DataExportJob.objects.filter(pk=job.pk).update(expires_at=timezone.now()-timedelta(seconds=1));job.refresh_from_db()
  with self.assertRaises(ValidationError):download_authorized(self.engineer,job)
 def test_client_cannot_export_people_or_internal_history(self):
  p=self.engineer.profile;p.role=Profile.Roles.CLIENT;p.save()
  for section in ['people','review_history','documents']:
   with self.assertRaises(PermissionDenied):request_export(self.engineer,section,request_key=str(uuid.uuid4()))
 def test_formula_prefixes_and_illegal_xml_controls_are_inert(self):
  for s in ['=1+2',' +cmd','\t=1','-2','@SUM(1)'] :self.assertTrue(safe_cell(s).startswith("'"))
  self.assertEqual(safe_cell('A\x00B'),'AB')
 def test_http_enqueue_csrf_owner_download_and_persistence(self):
  self.client.force_login(self.engineer)
  r=self.client.post('/exports/',{'section':'tasks','request_key':str(uuid.uuid4())});self.assertEqual(r.status_code,302)
  job=DataExportJob.objects.get(owner=self.engineer);self.assertContains(self.client.get('/exports/'),'Queued')
  process_next();job.refresh_from_db();r=self.client.get(f'/exports/{job.pk}/download/');self.assertEqual(r.status_code,200);r.close()
  self.client.force_login(self.stranger);self.assertEqual(self.client.get(f'/exports/{job.pk}/download/').status_code,404)
 def test_interrupted_lease_recovers_and_completed_job_is_not_reprocessed(self):
  from .export_models import DataExportWorkerLease
  job=self.export();old=uuid.uuid4();DataExportJob.objects.filter(pk=job.pk).update(status='running',lease_token=old,lease_until=timezone.now()-timedelta(minutes=1))
  DataExportWorkerLease.objects.create(key='data-exports',token=old,expires_at=timezone.now()-timedelta(minutes=1))
  self.assertTrue(process_next());job.refresh_from_db();self.assertEqual(job.status,'ready',job.error);self.assertEqual(job.attempts,1)
  self.assertFalse(process_next());self.assertEqual(DataExportJob.objects.count(),1)
 def test_active_worker_cannot_be_claimed_twice(self):
  from .export_models import DataExportWorkerLease
  self.export();DataExportWorkerLease.objects.create(key='data-exports',token=uuid.uuid4(),expires_at=timezone.now()+timedelta(minutes=1))
  self.assertFalse(process_next());self.assertEqual(DataExportJob.objects.get().status,'queued')
 def test_revocation_before_worker_fails_safely_without_output(self):
  job=self.export();p=self.engineer.profile;p.is_locked=True;p.save();process_next();job.refresh_from_db()
  self.assertEqual(job.status,'failed');self.assertFalse(job.file_name);self.assertIn('Access changed',job.error)
 def test_request_quota_and_failed_retry_are_bounded_idempotent(self):
  from .export_service import retry
  from unittest.mock import patch
  job=self.export();self.export()
  with self.assertRaises(ValidationError):self.export()
  with patch('core.export_service._workbook',side_effect=OSError('private disk path must not leak')):self.assertTrue(process_next())
  job.refresh_from_db();self.assertEqual(job.status,'failed');self.assertNotIn('private disk',job.error)
  retry(self.engineer,job);retry(self.engineer,job);self.assertEqual(DataExportJob.objects.count(),2)
 def test_expiry_worker_deletes_only_artifact_and_keeps_history(self):
  from .export_service import expire_exports
  job=self.export();process_next();job.refresh_from_db();path=download_authorized(self.engineer,job)
  DataExportJob.objects.filter(pk=job.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
  self.assertEqual(expire_exports(),1);self.assertFalse(path.exists());self.assertTrue(WorkAssignment.objects.filter(pk=self.task.pk).exists());job.refresh_from_db();self.assertEqual(job.status,'expired')
 def test_post_requires_csrf_and_never_generates_inline(self):
  from django.test import Client
  from unittest.mock import patch
  client=Client(enforce_csrf_checks=True);client.force_login(self.engineer)
  self.assertEqual(client.post('/exports/',{'section':'tasks','request_key':str(uuid.uuid4())}).status_code,403)
  self.client.force_login(self.engineer)
  with patch('core.export_service._workbook') as generation:
   self.assertEqual(self.client.post('/exports/',{'section':'tasks','request_key':str(uuid.uuid4())}).status_code,302);generation.assert_not_called()
 def test_current_expired_labels_do_not_claim_queued_or_allow_download(self):
  job=self.export();DataExportJob.objects.filter(pk=job.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
  self.client.force_login(self.engineer);response=self.client.get('/exports/')
  self.assertContains(response,'Expired');self.assertNotContains(response,'>Queued<',html=False)
 def test_large_cell_budget_fails_before_storage_exhaustion(self):
  from unittest.mock import patch
  job=self.export()
  with patch('core.export_service.MAX_TEXT_BYTES',4):process_next()
  job.refresh_from_db();self.assertEqual(job.status,'failed');self.assertIn('text size',job.error)
 def checklist(self):
  from .models import Checklist
  return Checklist.objects.create(user=self.engineer,project=self.project,site_id='EX-01',schema_snapshot={'sections':[{'id':'general','title':'General','fields':[{'id':'name','label':'Site name','type':'text','required':True}]}]},answer_data={'custom':{'name':'Verified record'}},review_history=[{'action':'returned','reason':'Real correction reason','at':'2026-11-07'}])
 def test_checklist_photo_document_metadata_exports_keep_originals_and_exclude_ai_payloads(self):
  from .models import PhotoEvidence,SurveyDocument
  from .export_service import rows
  c=self.checklist()
  photo=PhotoEvidence.objects.create(checklist=c,uploaded_by=self.engineer,filename='panel.jpg',sha256='a'*64,original='retained/photo.jpg',preview='retained/thumb.jpg',group='electrical',metadata={'captured_at':'2026-11-07','gps':{'latitude':24,'longitude':46}},analysis_metadata={'internal_private':'Never export AI internals'})
  doc=SurveyDocument.objects.create(checklist=c,uploaded_by=self.engineer,filename='sketch.pdf',sha256='b'*64,content_type='application/pdf',size=10,original='retained/sketch.pdf')
  for section,expected in [('checklists','Verified record'),('photos','panel.jpg'),('documents','sketch.pdf')]:
   job,_=request_export(self.engineer,section,request_key=uuid.uuid4());process_next();job.refresh_from_db();self.assertEqual(job.status,'ready',job.error)
   book=load_workbook(download_authorized(self.engineer,job),read_only=True);data=str(list(book['Data'].values));book.close()
   self.assertIn(expected,data);self.assertNotIn('internal_private',data);self.assertNotIn('retained/',data)
  photo.refresh_from_db();doc.refresh_from_db();self.assertEqual(photo.original.name,'retained/photo.jpg');self.assertEqual(doc.original.name,'retained/sketch.pdf')
 def test_platform_owner_is_administrative_only_and_company_admin_history_is_scoped(self):
  from .export_service import catalog,rows
  owner=User.objects.create_superuser('platform',email='owner@example.invalid',password='test-only')
  self.assertEqual(set(catalog(owner)),{'projects','clients','people'})
  with self.assertRaises(PermissionDenied):request_export(owner,'checklists',request_key=uuid.uuid4())
  self.checklist();p=self.engineer.profile;p.role=Profile.Roles.ADMIN;p.save()
  job,_=request_export(self.engineer,'review_history',request_key=uuid.uuid4());self.assertIn('Real correction reason',str(list(rows(self.engineer,job))))
 def test_ready_record_is_immutable_through_normal_model_save(self):
  job=self.export();process_next();job.refresh_from_db();job.row_count+=1
  with self.assertRaises(ValidationError):job.save()
 def test_download_columns_reference_requires_current_role(self):
  self.client.force_login(self.engineer)
  r=self.client.get('/exports/columns/tasks/');self.assertEqual(r.status_code,200);r.close()
  self.assertEqual(self.client.get('/exports/columns/people/').status_code,404)
 def test_worker_command_once_processes_real_saved_job(self):
  from django.core.management import call_command
  job=self.export();call_command('run_data_export_worker',once=True);job.refresh_from_db();self.assertEqual(job.status,'ready',job.error)
 def test_inventory_catalogs_export_only_owned_reported_values_without_units_inference(self):
  from .models import DCPowerSystemData,TowerEquipment,ElectricalData,Checklist
  c=self.checklist();foreign=Checklist.objects.create(user=self.stranger,project=self.foreign,site_id='FOREIGN-INVENTORY',schema_snapshot=c.schema_snapshot)
  for site in [c,foreign]:
   DCPowerSystemData.objects.create(checklist=site,row_number=1,field_label='Rectifier',field_value='=2+2' if site==c else 'FOREIGNSECRET')
   TowerEquipment.objects.create(checklist=site,row_number=1,operator_type='STC',equipment_type='ANTENNA',model_name='Owned antenna' if site==c else 'FOREIGNSECRET',height='reported:12 m',azimuth='120 degrees')
   ElectricalData.objects.create(checklist=site,row_number=1,voltage='reported:230 V' if site==c else 'FOREIGNSECRET',current_r='5 A')
  for section,expected in [('dc_power',"'=2+2"),('tower_equipment','reported:12 m'),('electrical','reported:230 V')]:
   job,_=request_export(self.engineer,section,request_key=uuid.uuid4());process_next();job.refresh_from_db();self.assertEqual(job.status,'ready',job.error)
   book=load_workbook(download_authorized(self.engineer,job),read_only=True,data_only=False);data=list(book['Data']);text=str([[cell.value for cell in row] for row in data]);self.assertIn(expected,text);self.assertNotIn('FOREIGNSECRET',text);self.assertTrue(all(cell.data_type!='f' for row in data for cell in row));book.close()
  p=self.engineer.profile;p.role=Profile.Roles.CLIENT;p.save()
  for section in ['dc_power','tower_equipment','electrical']:
   with self.assertRaises(PermissionDenied):request_export(self.engineer,section,request_key=uuid.uuid4())
 def test_replayed_http_request_reports_actual_ready_state_not_false_queue(self):
  from django.contrib.messages import get_messages
  self.client.force_login(self.engineer);key=str(uuid.uuid4());data={'section':'tasks','request_key':key}
  self.assertEqual(self.client.post('/exports/',data).status_code,302);self.client.get('/exports/');process_next()
  response=self.client.post('/exports/',data)
  notes=[str(message) for message in get_messages(response.wsgi_request)]
  self.assertTrue(any('Ready' in note for note in notes),notes)
  self.assertFalse(any(note.startswith('Export queued.') for note in notes),notes)
  self.assertEqual(DataExportJob.objects.filter(owner=self.engineer).count(),1)
