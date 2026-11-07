"""R01: public-write authority survives diagnostics, torn journals and restarts."""
from contextlib import closing
import copy,json,sqlite3
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase
from . import test_hostinger_delivery as fixtures
HEAD,OLD,MERGE,IMAGES=fixtures.HEAD,fixtures.OLD,fixtures.MERGE,fixtures.IMAGES

class PublicWriteBoundaryTests(SimpleTestCase):
 setUp=fixtures.SavedDataHostingerDeliveryTests.setUp
 tearDown=fixtures.SavedDataHostingerDeliveryTests.tearDown
 rows=fixtures.SavedDataHostingerDeliveryTests.rows
 active=fixtures.SavedDataHostingerDeliveryTests.active
 def publish_and_fail(self,failure='public_opening',interrupt=True):
  original=self.host.open_public
  def write(env):
   original(env)
   if env['ISURVIX_RELEASE_ID']==HEAD:
    target=Path(env['ISURVIX_DATA_DIRECTORY'])
    with closing(sqlite3.connect(target/'database.sqlite3')) as db,db:db.execute("insert into decisions values(2,'ACCEPTED_AFTER_PUBLIC_OPEN')")
    (target/'media/accepted-after-opening.jpg').write_bytes(b'SYNTHETIC accepted evidence after opening')
  self.host.open_public=write
  if failure=='public_opening':self.host.fail='late-sqlite'
  def hook(phase,state):
   if phase=='completed' and failure=='completed':raise ValueError('Synthetic completed receipt failure')
   if phase=='failure_recorded' and interrupt:raise KeyboardInterrupt('Synthetic controller interruption')
  self.engine.hook=hook
  if interrupt:
   with self.assertRaises(KeyboardInterrupt):self.engine.run(self.candidate)
  else:self.engine.run(self.candidate)
  self.target=Path(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY'])
 def assert_no_rewind_on_restart(self):
  env_before=self.delivery.read_env(self.environment);opens=self.host.calls.count('open-public');migrations=self.host.calls.count('migrate')
  self.host.fail=None
  fresh=self.delivery.Engine(self.work,self.environment,self.host)
  with patch.object(self.delivery.backup,'restore_backup',side_effect=AssertionError('A post-public restart must not activate a backup')):
   try:result=fresh.run(self.candidate)
   except self.delivery.DeliveryError as error:self.assertEqual(str(error),'operator_recovery_required')
   else:self.assertEqual(result['status'],'operator_recovery_required')
  self.assertFalse(self.host.public);self.assertEqual(self.delivery.read_env(self.environment),env_before)
  self.assertEqual(self.rows(self.target),[(1,'HUMAN_APPROVED'),(2,'ACCEPTED_AFTER_PUBLIC_OPEN')])
  self.assertEqual((self.target/'media/accepted-after-opening.jpg').read_bytes(),b'SYNTHETIC accepted evidence after opening')
  self.assertEqual((self.target/'media/original.jpg').read_bytes(),b'unchanged-photo-original')
  self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')]);self.assertEqual(self.host.calls.count('open-public'),opens);self.assertEqual(self.host.calls.count('migrate'),migrations)
 def legacy(self,explicit_false=False):
  value=self.active()
  if explicit_false:value['public_writes_possible']=False
  else:value.pop('public_writes_possible',None)
  self.delivery.atomic(self.work/'active.json',value);self.delivery.atomic(Path(value['transaction'])/'journal.json',value)
 def test_public_error_diagnostic_interruption_restarts_without_rewinding(self):
  self.publish_and_fail();self.assertEqual(self.active()['phase'],'failure_recorded');self.assert_no_rewind_on_restart()
 def test_completed_receipt_error_diagnostic_interruption_keeps_public_boundary(self):
  self.publish_and_fail('completed');self.assertEqual(self.active()['failure_phase'],'completed');self.assert_no_rewind_on_restart()
 def test_legacy_diagnostic_with_public_failure_phase_remains_readable_and_frozen(self):
  self.publish_and_fail();self.legacy();self.assert_no_rewind_on_restart()
 def test_legacy_explicit_false_marker_does_not_override_completed_failure_phase(self):
  self.publish_and_fail('completed');self.legacy(explicit_false=True);self.assert_no_rewind_on_restart()
 def test_phase_marker_is_monotonic_even_if_later_diagnostics_replace_failure_phase(self):
  self.publish_and_fail();state=self.active();fresh=self.delivery.Engine(self.work,self.environment,self.host)
  state['failure_phase']='failure_recorded';fresh.phase(state,'diagnostics_retried')
  self.assertIs(state.get('public_writes_possible'),True);self.assert_no_rewind_on_restart()
 def test_direct_rollback_cannot_reactivate_backup_after_public_opening(self):
  self.publish_and_fail();self.host.fail=None
  with patch.object(self.delivery.backup,'restore_backup',side_effect=AssertionError('Public rollback must never restore older data')):
   result=self.engine.rollback(self.active())
  self.assertEqual(result['status'],'operator_recovery_required');self.assert_no_rewind_on_restart()
 def test_failure_diagnostic_write_error_still_stops_and_restart_freezes(self):
  actual=self.delivery.atomic
  def fail(path,value):
   if isinstance(value,dict) and value.get('phase')=='failure_recorded':raise OSError('Synthetic diagnostic disk failure')
   return actual(path,value)
  with patch.object(self.delivery,'atomic',side_effect=fail):
   with self.assertRaises(OSError):self.publish_and_fail(interrupt=False)
  self.target=Path(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY'])
  self.assertFalse(self.host.public,'Journal failure must not leave the newly opened writer running')
  self.assert_no_rewind_on_restart()
 def test_freeze_journal_error_does_not_erase_earlier_public_marker(self):
  actual=self.delivery.atomic
  def fail(path,value):
   if isinstance(value,dict) and value.get('phase')=='operator_recovery_required':raise OSError('Synthetic freeze disk failure')
   return actual(path,value)
  with patch.object(self.delivery,'atomic',side_effect=fail):
   with self.assertRaises(OSError):self.publish_and_fail(interrupt=False)
  self.target=Path(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']);self.assertFalse(self.host.public);self.assert_no_rewind_on_restart()
 def test_stop_failure_during_freeze_never_allows_restart_rollback(self):
  original=self.host.stop;count=[0]
  def fail_once():
   if self.host.running==HEAD and self.host.public and count[0]==0:count[0]+=1;raise OSError('Synthetic stop failure')
   return original()
  with patch.object(self.host,'stop',side_effect=fail_once):
   with self.assertRaises(OSError):self.publish_and_fail(interrupt=False)
  self.target=Path(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']);self.assert_no_rewind_on_restart()
 def test_transaction_journal_public_marker_wins_over_stale_active_index(self):
  self.publish_and_fail();latest=self.active();stale=copy.deepcopy(latest);stale['phase']='private_ready';stale.pop('failure_phase',None);stale['public_writes_possible']=False
  self.delivery.atomic(self.work/'active.json',stale);self.assert_no_rewind_on_restart()
 def test_stale_completed_active_cannot_hide_later_failure_transaction_journal(self):
  self.publish_and_fail('completed');stale=copy.deepcopy(self.active());stale['phase']='completed';stale.pop('failure_phase',None)
  self.delivery.atomic(self.work/'active.json',stale);self.assert_no_rewind_on_restart()
 def test_public_reopening_during_rollback_has_its_own_durable_boundary(self):
  self.host.fail='private-health';original=self.host.open_public
  def reopen(env):
   original(env)
   if env['ISURVIX_RELEASE_ID']==OLD:
    self.target=Path(env['ISURVIX_DATA_DIRECTORY'])
    with closing(sqlite3.connect(self.target/'database.sqlite3')) as db,db:db.execute("insert into decisions values(2,'ACCEPTED_AFTER_PUBLIC_OPEN')")
    (self.target/'media/accepted-after-opening.jpg').write_bytes(b'SYNTHETIC accepted evidence after opening')
    raise KeyboardInterrupt('Synthetic interruption after recovered service accepts writes')
  self.host.open_public=reopen
  with self.assertRaises(KeyboardInterrupt):self.engine.run(self.candidate)
  self.host.open_public=original;self.assert_no_rewind_on_restart()
 def test_successful_prior_release_does_not_block_a_later_guarded_update(self):
  self.engine.run(self.candidate);next_candidate={**self.candidate,'pr':35,'head_sha':'d'*40,'merge_sha':'e'*40,'supported_from':[HEAD],'images':{'app':'sha256:'+'5'*64,'nginx':IMAGES['nginx']}}
  result=self.engine.run(next_candidate);self.assertEqual(result['status'],'completed');self.assertEqual(result['release'],'d'*40)
