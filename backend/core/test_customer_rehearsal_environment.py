"""CI helper opt-in must survive a real subprocess environment boundary.

Portable execution uses Git Bash env -i on Windows. Ubuntu additionally runs
actual passwordless sudo, without replacing the helper or its safety guard.
"""
import json,os,shlex,shutil,subprocess,sys,unittest
from pathlib import Path
from django.test import SimpleTestCase

ROOT=Path(__file__).resolve().parents[2]
PROBE=r'''
import importlib.util,json,os,sys
from pathlib import Path
path=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('real_rehearsal_guard',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
try:
 module.verify_post_activation({},Path('unused'),source_database=Path('unused'),preactivation_before={},preactivation_proof={},expected_release='invalid',expected_notes={},scratch_directory=path.parent)
except ValueError as error:
 print(json.dumps({'guard':str(error),'opt_in':os.environ.get('ISURVIX_DISPOSABLE_REHEARSAL'),'uid':os.geteuid() if hasattr(os,'geteuid') else None}))
'''

class CustomerRehearsalEnvironmentTests(SimpleTestCase):
 def prefix(self):
  script=(ROOT/'deploy/verify_updates.sh').read_text()
  # Select the actual heredoc whose body invokes the phase-aware CI verifier.
  import re
  blocks=re.findall(r"(^[^\n]*<<'PY')\n(.*?)\nPY(?:\n|$)",script,re.M|re.S)
  command=next(command for command,body in blocks if 'rehearsal_retention.verify_post_activation' in body)
  words=shlex.split(command.split("<<'PY'")[0]);self.assertEqual(words[0],'sudo')
  python=words.index('/usr/bin/python3')
  return words[1:python]
 def probe(self,command,environment):
  result=subprocess.run(command,capture_output=True,text=True,env=environment,timeout=15)
  self.assertEqual(result.returncode,0,result.stderr[-500:]);return json.loads(result.stdout)
 def test_actual_selected_invocation_explicitly_opted_in_under_clean_environment(self):
  prefix=self.prefix();helper=str(ROOT/'deploy/customer/rehearsal_retention.py')
  if os.name=='nt':
   bash=Path(r'C:\Program Files\Git\bin\bash.exe')
   if not bash.is_file():self.skipTest('Git Bash env -i is unavailable; Linux sudo integration remains separate')
   keep=['PATH=/usr/bin:/bin',*[name+'='+os.environ[name] for name in ('SystemRoot','WINDIR') if name in os.environ]]
   command=[str(bash),'-lc',shlex.join(['env','-i',*keep,*prefix,sys.executable,'-c',PROBE,helper])]
  else:
   env=shutil.which('env')
   if not env:self.skipTest('env executable is unavailable')
   command=[env,'-i','PATH=/usr/bin:/bin',*prefix,sys.executable,'-c',PROBE,helper]
  environment=dict(os.environ);environment['ISURVIX_DISPOSABLE_REHEARSAL']='yes'
  result=self.probe(command,environment)
  self.assertEqual(result['opt_in'],'yes','The selected CI invocation loses its explicit opt-in at an environment boundary')
  self.assertEqual(result['guard'],'An exact immutable target release is required.','The opt-in guard must pass while the next real validation remains enforced')
 @unittest.skipUnless(os.name=='posix','Actual sudo boundary is Linux-only')
 def test_real_sudo_drops_inherited_opt_in_but_selected_explicit_invocation_reaches_next_guard(self):
  sudo=shutil.which('sudo');environment=dict(os.environ);environment['ISURVIX_DISPOSABLE_REHEARSAL']='yes'
  available=bool(sudo) and subprocess.run([sudo,'-n','true'],capture_output=True,timeout=5).returncode==0
  if not available:
   if os.environ.get('GITHUB_ACTIONS')=='true':self.fail('Linux GitHub acceptance requires passwordless sudo')
   self.skipTest('This local Linux host does not provide passwordless sudo')
  helper=str(ROOT/'deploy/customer/rehearsal_retention.py')
  negative=self.probe([sudo,'-n','/usr/bin/python3','-c',PROBE,helper],environment)
  self.assertEqual(negative['uid'],0);self.assertIsNone(negative['opt_in']);self.assertIn('explicit disposable rehearsal',negative['guard'])
  positive=self.probe([sudo,'-n',*self.prefix(),'/usr/bin/python3','-c',PROBE,helper],environment)
  self.assertEqual(positive['uid'],0);self.assertEqual(positive['opt_in'],'yes');self.assertEqual(positive['guard'],'An exact immutable target release is required.')
