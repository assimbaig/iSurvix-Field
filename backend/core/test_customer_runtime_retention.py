"""Regression for migration gate versus post-login customer rehearsal checks."""
import ast,importlib.util,json,os,shutil,sqlite3,subprocess,sys,tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from .test_invitation_email_upgrade import BUILD,ROOT

class CustomerPostLoginRetentionTests(SimpleTestCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();parent=ROOT/'.local/customer-post-login-retention';parent.mkdir(parents=True,exist_ok=True)
  cls.tmp=tempfile.TemporaryDirectory(dir=parent);cls.addClassCleanup(cls.tmp.cleanup);cls.root=Path(cls.tmp.name)
  build=BUILD.replace("call_command('migrate','core','0060_invitation_email_delivery'","call_command('migrate','core','0067_installed_release_history'")
  build=build.replace("User.objects.create_user('synthetic-email-upgrade',password=None)","call_command('migrate','sessions',interactive=False,verbosity=0)\n User.objects.create_user('synthetic-email-upgrade',password='Synthetic-Login-397!')")
  build=build.replace('before=proof.snapshot(db);',"\n with sqlite3.connect(work/'source.sqlite3') as persisted:connection.connection.backup(persisted)\n before=proof.snapshot(db);")
  build=build.replace('connections.close_all()',"""
 gate=proof.assert_retained(before,db,source_database=work/'source.sqlite3')
 (work/'gate-proof.json').write_text(json.dumps(gate))
 # Execute actual sign-in, rather than inventing the InstalledRelease side effect.
 settings.ROOT_URLCONF='checklist.urls_local';settings.ALLOWED_HOSTS=['testserver'];settings.SECURE_SSL_REDIRECT=False;settings.ISURVIX_RELEASE_ID='a'*40
 from django.test import Client
 client=Client();response=client.post('/login/',{'username':'synthetic-email-upgrade','password':'Synthetic-Login-397!'})
 assert response.status_code==302,response.status_code
 from core.release_history_models import InstalledRelease
 assert InstalledRelease.objects.count()==1
 from core.release_note_content import NOTES
 (work/'notes.json').write_text(json.dumps({**NOTES,'changes':list(NOTES['changes'])}))
 with sqlite3.connect(db) as persisted:connection.connection.backup(persisted)
 connections.close_all()
""")
  result=subprocess.run([sys.executable,'-c',build,str(ROOT),str(cls.root),'0064_company_notification_settings'],capture_output=True,text=True,timeout=90)
  if result.returncode:raise AssertionError(result.stderr[-1800:])
 def fixture(self):
  def module(name,file):
   spec=importlib.util.spec_from_file_location(name,file);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
  proof=module('strict_runtime_gate',ROOT/'deploy/customer/upgrade_fixture.py')
  runtime=module('runtime_phase_verifier',ROOT/'deploy/customer/rehearsal_retention.py')
  target=self.root/(self._testMethodName+'.sqlite3');shutil.copyfile(self.root/'target.sqlite3',target)
  before=json.loads((self.root/'before.json').read_text())
  options={'source_database':self.root/'source.sqlite3','preactivation_before':before,'preactivation_proof':json.loads((self.root/'gate-proof.json').read_text()),'expected_release':'a'*40,'expected_notes':json.loads((self.root/'notes.json').read_text()),'scratch_directory':self.root}
  return proof,runtime,before,target,options
 def test_real_login_keeps_migration_gate_strict_but_runtime_check_validates_known_addition(self):
  proof,runtime,before,target,options=self.fixture()
  with self.assertRaises(ValueError):proof.assert_retained(before,target,source_database=options['source_database'])
  old=target.read_bytes()
  with patch.dict(os.environ,{'ISURVIX_DISPOSABLE_REHEARSAL':'yes'}):result=runtime.verify_post_activation(before,target,**options)
  self.assertEqual(result['runtime_additions'],{'core_installedrelease':1,'core_dataexportworkerlease':0})
  self.assertEqual(target.read_bytes(),old,'The live rehearsal database must not be edited to make a test pass')
 def test_wrong_notes_extra_history_active_lease_and_changed_old_record_are_rejected(self):
  mutations=["UPDATE core_installedrelease SET version='999.0'", "UPDATE core_installedrelease SET changes='[\"Fabricated\"]'", "INSERT INTO core_installedrelease(release_key,version,title,release_date,changes,first_seen_at) SELECT 'b'||substr(release_key,2),version,title,release_date,changes,first_seen_at FROM core_installedrelease", "INSERT INTO core_dataexportworkerlease(key,token,expires_at) VALUES('data-exports','11111111111111111111111111111111','2030-01-01')", "UPDATE auth_user SET is_superuser=1"]
  for sql in mutations:
   _,runtime,before,target,options=self.fixture()
   with closing(sqlite3.connect(target)) as db,db:db.executescript(sql)
   with self.subTest(sql=sql),patch.dict(os.environ,{'ISURVIX_DISPOSABLE_REHEARSAL':'yes'}),self.assertRaises(ValueError):runtime.verify_post_activation(before,target,**options)
 def test_idle_singleton_is_allowed_only_after_real_empty_migration_proof(self):
  _,runtime,before,target,options=self.fixture()
  with closing(sqlite3.connect(target)) as db,db:db.execute("INSERT INTO core_dataexportworkerlease(key,token,expires_at) VALUES('data-exports',NULL,NULL)")
  with patch.dict(os.environ,{'ISURVIX_DISPOSABLE_REHEARSAL':'yes'}):self.assertEqual(runtime.verify_post_activation(before,target,**options)['runtime_additions']['core_dataexportworkerlease'],1)
  options['preactivation_proof']['retained_rows_sha256']='0'*64
  with patch.dict(os.environ,{'ISURVIX_DISPOSABLE_REHEARSAL':'yes'}),self.assertRaises(ValueError):runtime.verify_post_activation(before,target,**options)
 def test_verifier_requires_disposable_mode(self):
  _,runtime,before,target,options=self.fixture()
  with patch.dict(os.environ,{'ISURVIX_DISPOSABLE_REHEARSAL':'no'}),self.assertRaises(ValueError):runtime.verify_post_activation(before,target,**options)
 def test_release_notes_are_parsed_as_data_without_executing_candidate_code(self):
  _,runtime,_,_,_=self.fixture();source=self.root/'malicious-notes.py';marker=self.root/'must-not-exist.txt'
  source.write_text("NOTES={'version': __import__('pathlib').Path("+repr(str(marker))+").write_text('not allowed'), 'title':'Bad','date':'2026-11-07','changes':['Bad']}\n")
  with self.assertRaises(ValueError):runtime.load_release_notes(source)
  self.assertFalse(marker.exists())
  source.write_text("NOTE_ID='reference-only'\nNOTES={'note_id':NOTE_ID,'version':'1.3','title':'Safe notes','date':'2026-11-07','changes':('First','Second')}\n")
  self.assertEqual(runtime.load_release_notes(source),{'version':'1.3','title':'Safe notes','date':'2026-11-07','changes':['First','Second']})
 def test_harness_keeps_post_login_verification_separate_from_production_gate(self):
  script=(ROOT/'deploy/verify_updates.sh').read_text()
  login=script.index("owner=login('synthetic_owner')")
  replay=script.index('> "$work/repeat-result.json"')
  quiesce=script.index('stop --timeout 60 proxy web')
  compare=script.index('rehearsal_retention.verify_post_activation')
  self.assertLess(login,replay);self.assertLess(replay,quiesce);self.assertLess(quiesce,compare)
  self.assertIn("sealed['artifacts'][name]",script)
  updater=(ROOT/'deploy/customer/updater.py').read_text()
  self.assertLess(updater.index('proof = reviewed_retention.assert_retained('),updater.index("_phase(transaction, state, 'checking-candidate')"))
  import re
  blocks=re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)",script,re.S)
  self.assertGreater(len(blocks),5)
  for block in blocks:ast.parse(block)
 def test_metadata_version_requires_the_app_canonical_ascii_grammar(self):
  _,runtime,_,_,_=self.fixture();source=self.root/'invalid-version-notes.py'
  for version in ['01.3','1.03','١.٣','1.3.01']:
   source.write_text('NOTES='+repr({'version':version,'title':'Notes','date':'2026-11-07','changes':['One change']}),encoding='utf-8')
   with self.subTest(version=version),self.assertRaises(ValueError):runtime.load_release_notes(source)
