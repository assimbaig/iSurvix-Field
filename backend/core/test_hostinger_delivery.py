"""Guarded hosting delivery: controlled GitHub/runner fixtures, real saved data."""
import copy
from contextlib import closing, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import shutil
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from unittest.mock import patch
from zipfile import ZipFile

from django.test import SimpleTestCase

ROOT=Path(__file__).resolve().parents[2]
HEAD='a'*40
MERGE='b'*40
OLD='c'*40
TREE='d'*40
REPO='assimbaig/iSurvix-Field'
BRANCH='feat/ai-settings-routing-20261031'
IMAGES={'app':'sha256:'+'1'*64,'nginx':'sha256:'+'2'*64}


def module():
    spec=importlib.util.spec_from_file_location('trusted_hostinger_delivery',ROOT/'deploy/hostinger/controller.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


class API:
    def __init__(self):
        self.pr={'number':34,'merged':True,'state':'closed','merged_at':'2026-11-04T20:00:00Z','merge_commit_sha':MERGE,'merged_by':{'login':'assimbaig'},'head':{'sha':HEAD,'repo':{'full_name':REPO}},'base':{'ref':BRANCH,'repo':{'full_name':REPO}}}
        self.current=MERGE;self.head_tree=TREE;self.merge_tree=TREE;self.reviews=[];self.runs=[]
    def get(self,path):
        if path.endswith('/pulls/34'):return copy.deepcopy(self.pr)
        if '/git/ref/heads/' in path:return {'object':{'sha':self.current}}
        if path.endswith('/git/commits/'+HEAD):return {'sha':HEAD,'tree':{'sha':self.head_tree}}
        if path.endswith('/git/commits/'+MERGE):return {'sha':MERGE,'tree':{'sha':self.merge_tree}}
        raise AssertionError('Unexpected controlled API read')
    def pages(self,path,key=None):
        if '/reviews' in path:return copy.deepcopy(self.reviews)
        if '/actions/runs?' in path:return copy.deepcopy(self.runs)
        raise AssertionError('Unexpected controlled API pagination')


class HostingerAuthorityTests(SimpleTestCase):
    def setUp(self):self.delivery=module();self.api=API()
    def test_owner_merge_authorizes_exact_pr_head_not_relabelled_merge(self):
        result=self.delivery.authorize(self.api,34)
        self.assertEqual(result['head_sha'],HEAD);self.assertEqual(result['merge_sha'],MERGE)
        self.assertEqual(result['approval'],'owner_merge')
    def test_other_merger_needs_latest_owner_approval_on_exact_head(self):
        self.api.pr['merged_by']={'login':'maintainer'}
        for reviews in [[],[{'id':1,'user':{'login':'assimbaig'},'commit_id':OLD,'state':'APPROVED'}],[{'id':1,'user':{'login':'assimbaig'},'commit_id':HEAD,'state':'CHANGES_REQUESTED'}]]:
            self.api.reviews=reviews
            with self.assertRaises(ValueError):self.delivery.authorize(self.api,34)
        self.api.reviews=[{'id':1,'user':{'login':'assimbaig'},'commit_id':HEAD,'state':'APPROVED'}]
        self.assertEqual(self.delivery.authorize(self.api,34)['approval'],'owner_review')
        self.api.reviews.append({'id':2,'user':{'login':'assimbaig'},'commit_id':HEAD,'state':'DISMISSED'})
        with self.assertRaises(ValueError):self.delivery.authorize(self.api,34)
    def test_fork_unmerged_wrong_branch_stale_branch_and_changed_merge_tree_rejected(self):
        for mutate in [lambda a:a.pr['head'].update(repo={'full_name':'attacker/fork'}),lambda a:a.pr.update(merged=False),lambda a:a.pr['base'].update(ref='main'),lambda a:setattr(a,'current',OLD),lambda a:setattr(a,'merge_tree',OLD)]:
            api=API();mutate(api)
            with self.assertRaises(ValueError):self.delivery.authorize(api,34)
    def test_request_rejects_caller_paths_commands_urls_duplicates_and_missing_credentials(self):
        for payload in [{'pr':34},{'pr':34,'github_token':''},{'pr':True,'github_token':'fixture-token-1234567890'},{'pr':34,'github_token':'fixture-token-1234567890','command':'rm -rf /'},{'pr':34,'github_token':'fixture-token-1234567890','artifact_url':'http://127.0.0.1/private'}]:
            with self.assertRaises(ValueError):self.delivery.read_request(io.BytesIO(json.dumps(payload).encode()))
        with self.assertRaises(ValueError):self.delivery.read_request(io.BytesIO(b'{"pr":34,"pr":35,"github_token":"fixture-token-1234567890"}'))
        self.assertEqual(self.delivery.read_request(io.BytesIO(b'{"pr":34,"github_token":"fixture-token-1234567890"}'))['pr'],34)
    def test_failed_or_unfinished_exact_source_check_blocks_delivery(self):
        self.api.runs=[dict(id=i,run_number=i,run_attempt=1,path=path,head_sha=HEAD,head_repository={'full_name':REPO},status='completed',conclusion='success',updated_at='2026-11-04T20:00:00Z') for i,path in enumerate(self.delivery.release_gate.REQUIRED_WORKFLOWS,1)]
        self.assertEqual(len(self.delivery.require_checks(self.api,HEAD)),3)
        self.api.runs[0]['conclusion']='failure'
        with self.assertRaises(ValueError):self.delivery.require_checks(self.api,HEAD)
        self.api.runs[0].update(status='in_progress',conclusion=None)
        with self.assertRaises(ValueError):self.delivery.require_checks(self.api,HEAD)
    def test_credential_transport_is_https_only_and_never_forwards_auth_to_storage(self):
        for url in ['http://blob.core.windows.net/a','https://api.github.com/private','https://blob.core.windows.net.attacker.example/a','https://127.0.0.1/a','https://user:pass@x.blob.core.windows.net/a']:
            with self.assertRaises(ValueError):self.delivery.storage_url(url)
        self.assertEqual(self.delivery.storage_url('https://safe.blob.core.windows.net/a?signed=private'),'https://safe.blob.core.windows.net/a?signed=private')


class ArtifactBindingTests(SimpleTestCase):
    def setUp(self):
        self.delivery=module();parent=ROOT/'.local/test-fixtures';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='hostinger-artifact-',dir=parent);self.root=Path(self.temp.name)
        self.api=API()
        self.api.runs=[dict(id=i,run_number=i,run_attempt=1,path=path,head_sha=HEAD,head_repository={'full_name':REPO},status='completed',conclusion='success',updated_at='2026-11-04T20:00:00Z') for i,path in enumerate(self.delivery.release_gate.REQUIRED_WORKFLOWS,1)]
        self.api.runs.append(dict(self.api.runs[0],id=10,run_number=10,path=self.delivery.SHARED_WORKFLOW))
        checks=self.delivery.require_checks(self.api,HEAD)
        package=self.root/'fixture/package';package.mkdir(parents=True)
        for name in self.delivery.consumer.REQUIRED_FILES:
            path=package/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((HEAD+'\n').encode() if name=='release/RELEASE' else b'raise RuntimeError("Candidate installer must never execute as root")\n')
        manifest={'format':self.delivery.consumer.FORMAT,'status':'draft-for-review','owner_release_approved':False,'release_id':HEAD,'target':{'os':'linux','architecture':'amd64'},'images':IMAGES,'approval_holds':[],'files':{p.relative_to(package).as_posix():self.delivery.consumer._digest(p) for p in package.rglob('*') if p.is_file()}}
        (package/'manifest.json').write_text(json.dumps(manifest))
        digest=hashlib.sha256((package/'manifest.json').read_bytes()).hexdigest()
        proof={'release':HEAD,'fresh_install':True,'runtime_image_pulls':0,'restart_preserved_db_and_media':True,'upgrade_recovery_verified':True,'supported_from':[OLD],'images':IMAGES,'manifest_sha256':digest}
        self.record=self.delivery.release_gate.release_record(manifest,digest,checks,proof)
        (self.root/'fixture/shared').mkdir();(self.root/'fixture/shared/release.json').write_text(json.dumps(self.record))
        self.archive=self.root/'source.zip'
        with ZipFile(self.archive,'w') as z:
            for path in (self.root/'fixture').rglob('*'):
                if path.is_file():z.write(path,path.relative_to(self.root/'fixture').as_posix())
        self.metadata={'id':100,'name':'shared-release-candidate-'+HEAD,'expired':False,'size_in_bytes':self.archive.stat().st_size,'digest':'sha256:'+hashlib.sha256(self.archive.read_bytes()).hexdigest(),'workflow_run':{'id':10,'head_sha':HEAD}}
        get=self.api.get;pages=self.api.pages
        def fixture_get(path):
            if '/actions/artifacts/100' in path:return copy.deepcopy(self.metadata)
            return get(path)
        def fixture_pages(path,key=None):
            if '/actions/runs/10/artifacts' in path:return [copy.deepcopy(self.metadata)]
            return pages(path,key)
        self.api.get=fixture_get;self.api.pages=fixture_pages
        self.api.download=lambda identity,path,size,digest:shutil.copyfile(self.archive,path)
    def tearDown(self):self.temp.cleanup()
    def acquire(self):return self.delivery.acquire(self.api,self.delivery.authorize(self.api,34),self.root/'acquisitions')
    def test_real_package_consumer_checks_prebuilt_head_and_does_not_execute_candidate_installer(self):
        candidate=self.acquire()
        self.assertEqual(candidate['head_sha'],HEAD);self.assertEqual(candidate['merge_sha'],MERGE)
        self.assertEqual(candidate['images'],IMAGES);self.assertEqual(candidate['supported_from'],[OLD])
        self.assertEqual(candidate['artifact_sha256'],self.metadata['digest'][7:])
    def test_expired_wrong_source_and_failed_shared_producer_are_rejected(self):
        self.metadata['expired']=True
        with self.assertRaises(ValueError):self.acquire()
        self.metadata['expired']=False;self.metadata['workflow_run']['head_sha']=OLD
        with self.assertRaises(ValueError):self.acquire()
        self.metadata['workflow_run']['head_sha']=HEAD;self.api.runs[-1]['conclusion']='failure'
        with self.assertRaises(ValueError):self.acquire()
    def test_valid_outer_hash_cannot_hide_modified_inner_package_file(self):
        with ZipFile(self.archive) as z:members={name:z.read(name) for name in z.namelist()}
        members['package/release/RELEASE']=b'forged'
        with ZipFile(self.archive,'w') as z:
            for name,raw in members.items():z.writestr(name,raw)
        self.metadata.update(size_in_bytes=self.archive.stat().st_size,digest='sha256:'+hashlib.sha256(self.archive.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):self.acquire()
    def test_branch_advance_during_download_blocks_activation(self):
        def download(identity,path,size,digest):shutil.copyfile(self.archive,path);self.api.current=OLD
        self.api.download=download
        with self.assertRaises(ValueError):self.acquire()
    def test_missing_or_revoked_credential_does_not_create_candidate(self):
        self.api.get=lambda path:(_ for _ in ()).throw(ValueError('Controlled credential revoked'))
        with self.assertRaises(ValueError):self.acquire()
        self.assertFalse((self.root/'acquisitions').exists())
    def test_actual_transport_download_does_not_forward_api_authorization_to_storage(self):
        payload=self.archive.read_bytes();calls=[];token='fixture-token-1234567890'
        class Response(io.BytesIO):status=200
        class Opener:
            def open(inner,request,**kwargs):
                calls.append(request)
                if len(calls)==1:raise HTTPError(request.full_url,302,'redirect',{'Location':'https://safe.blob.core.windows.net/artifact?fixture-signature=private'},None)
                return Response(payload)
        with patch.object(self.delivery,'build_opener',return_value=Opener()):
            self.delivery.GitHub(token).download(100,self.root/'transport.zip',len(payload),hashlib.sha256(payload).hexdigest())
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0].get_header('Authorization'),'Bearer '+token)
        self.assertIsNone(calls[1].get_header('Authorization'))
        self.assertEqual((self.root/'transport.zip').read_bytes(),payload)
    def test_actual_transport_revoked_token_errors_are_redacted(self):
        token='fixture-token-1234567890'
        class Opener:
            def open(inner,request,**kwargs):raise HTTPError(request.full_url,401,'private '+token,{},None)
        with patch.object(self.delivery,'build_opener',return_value=Opener()):
            with self.assertRaises(ValueError) as denied:self.delivery.GitHub(token).get('/repos/'+REPO+'/pulls/34')
        self.assertNotIn(token,str(denied.exception));self.assertIn('credential_revoked',str(denied.exception))


class RuntimePolicyTests(SimpleTestCase):
    def setUp(self):self.delivery=module()
    def config(self):
        return {'services':{'web':{'image':IMAGES['app'],'user':'10001:10001','read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'ports':[],'volumes':[{'target':'/data','source':'/private/data','type':'bind'},{'target':'/run/isurvix-config/ifield_settings.py','source':'/private/settings.py','type':'bind','read_only':True}]},'proxy':{'image':IMAGES['nginx'],'user':'101:101','read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'ports':[{'host_ip':'127.0.0.1','published':'8080','target':8080},{'host_ip':'127.0.0.1','published':'8443','target':8443},{'host_ip':'0.0.0.0','published':'443','target':8443}],'volumes':[{'target':'/etc/nginx/nginx.conf','source':'/private/nginx.conf','type':'bind','read_only':True},{'target':'/data/static','source':'/private/data/static','type':'bind','read_only':True},{'target':'/tls','source':'/private/tls','type':'bind','read_only':True}]}},'secrets':{'django_secret_key':{'file':'/private/secret'}}}
    def test_no_new_privileges_public_web_or_private_media_mount_can_enter_runtime(self):
        self.delivery.validate_compose(self.config())
        for mutate in [lambda c:c['services']['web'].update(user='root'),lambda c:c['services']['web'].update(read_only=False),lambda c:c['services']['web'].update(ports=[{'published':'8000','target':8000}]),lambda c:c['services']['proxy']['volumes'].append({'source':'/private/data/media','target':'/media','read_only':True}),lambda c:c['services']['proxy']['ports'].append({'host_ip':'0.0.0.0','published':'8443','target':8443})]:
            value=self.config();mutate(value)
            with self.assertRaises(ValueError):self.delivery.validate_compose(value)
    def test_stop_requires_every_web_writer_to_be_stopped_not_restarting_or_paused(self):
        for state in ('running','restarting','paused'):
            host=self.delivery.Host({'environment_file':'/private/staging.env','project':'isurvix-staging','compose_files':['/trusted/base.yaml','/trusted/override.yaml']})
            def command(*args,**kwargs):
                if args[0]=='ps':return json.dumps([{'Service':'web','State':state}]).encode()
                return b''
            host.dc=command
            with self.subTest(state=state):
                with self.assertRaises(ValueError):host.stop()
    def test_ssh_session_limit_is_account_scoped_and_global_context_is_restored(self):
        text=(ROOT/'deploy/hostinger/sshd-deploy.conf.example').read_text()
        self.assertIn('Match User ifield-delivery',text)
        self.assertIn('    MaxSessions 1\n',text)
        self.assertTrue(text.rstrip().endswith('Match all'))
        self.assertNotIn('PermitUserEnvironment',text)


@unittest.skipUnless(os.name=='posix','Production select/os.read pipe deadlines require POSIX; Linux CI runs these real-pipe cases.')
class NativeRequestDeadlineTests(SimpleTestCase):
    def setUp(self):
        self.delivery=module();parent=ROOT/'.local/test-fixtures';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='delivery-request-pipe-',dir=parent);self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_stalled_incomplete_pipe_has_hard_body_deadline(self):
        read,write=os.pipe();os.write(write,b'{"pr":34')
        try:
            with os.fdopen(read,'rb',buffering=0) as stream:
                start=time.monotonic()
                with self.assertRaisesRegex(ValueError,'request_body_deadline'):self.delivery.read_request(stream,body_timeout=0.15)
                self.assertLess(time.monotonic()-start,1.5)
        finally:os.close(write)
    def test_partial_body_and_eof_are_read_without_losing_bytes(self):
        read,write=os.pipe();payload=b'{"pr":34,"github_token":"fixture-token-1234567890"}'
        def produce():
            os.write(write,payload[:10]);time.sleep(0.02);os.write(write,payload[10:]);os.close(write)
        thread=threading.Thread(target=produce);thread.start()
        with os.fdopen(read,'rb',buffering=0) as stream:self.assertEqual(self.delivery.read_request(stream,body_timeout=1)['pr'],34)
        thread.join(timeout=1);self.assertFalse(thread.is_alive())
    def test_only_one_receiver_can_wait_for_a_body(self):
        read,write=os.pipe();entered=threading.Event();errors=[]
        raw=os.fdopen(read,'rb',buffering=0)
        class Stream:
            def fileno(self):entered.set();return raw.fileno()
        def first():
            try:self.delivery.receive({'root':str(self.root)},Stream(),lambda request:None,body_timeout=0.4)
            except ValueError as error:errors.append(str(error))
        thread=threading.Thread(target=first);thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError,'another_delivery_is_active'):self.delivery.receive({'root':str(self.root)},io.BytesIO(b'{"pr":34,"github_token":"fixture-token-1234567890"}'),lambda request:None)
            thread.join(timeout=2);self.assertFalse(thread.is_alive());self.assertEqual(errors,['request_body_deadline'])
        finally:os.close(write);raw.close();thread.join(timeout=2)


class DisposableHostRehearsalGuardTests(SimpleTestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('host_delivery_rehearsal',ROOT/'deploy/hostinger/verify_delivery.py')
        self.rehearsal=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.rehearsal)
        parent=ROOT/'.local/test-fixtures';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='delivery-ci-guards-',dir=parent);self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_native_rehearsal_refuses_non_ci_existing_and_outside_work_before_mutation(self):
        good={'ISURVIX_DISPOSABLE_REHEARSAL':'yes','GITHUB_ACTIONS':'true','RUNNER_TEMP':str(self.root)}
        for env,work in [({},self.root/'new'),({**good,'ISURVIX_DISPOSABLE_REHEARSAL':'no'},self.root/'new'),(good,self.root),(good,self.root.parent/'outside')]:
            with self.assertRaises(ValueError):self.rehearsal.disposable(work,environ=env,uid=0,platform='posix')
        self.rehearsal.disposable(self.root/'new',environ=good,uid=0,platform='posix')
        self.assertFalse((self.root/'new').exists())
    def test_existing_native_upgrade_proof_must_bind_source_target_images_and_manifest(self):
        proof={'release':HEAD,'supported_from':[OLD],'images':IMAGES,'manifest_sha256':'e'*64,'upgrade_recovery_verified':True,'caught_failure_rolled_back':True,'interrupted_process_recovered':True}
        self.rehearsal.upgrade_proof(proof,OLD,HEAD,IMAGES,'e'*64)
        for key,value in [('release',MERGE),('supported_from',[]),('images',{}),('manifest_sha256','f'*64),('upgrade_recovery_verified',False),('interrupted_process_recovered',False)]:
            bad={**proof,key:value}
            with self.assertRaises(ValueError):self.rehearsal.upgrade_proof(bad,OLD,HEAD,IMAGES,'e'*64)
    def test_rejected_native_cli_does_not_write_or_chmod_an_existing_work_directory(self):
        before=self.root.stat().st_mode
        with patch.dict('os.environ',{'GITHUB_ACTIONS':'false'}),redirect_stdout(io.StringIO()):
            status=self.rehearsal.main(['--work',str(self.root),'--source-package',str(self.root/'source'),'--target-package',str(self.root/'target'),'--source-release',OLD,'--target-release',HEAD])
        self.assertEqual(status,2)
        self.assertFalse((self.root/'verification.json').exists())
        self.assertEqual(self.root.stat().st_mode,before)


class FixtureHost:
    def __init__(self,delivery):self.delivery=delivery;self.calls=[];self.fail=None;self.running=None;self.public=False
    def stop(self):self.calls.append('stop');self.public=False;self.running=None
    def preflight(self,env):self.calls.append('preflight')
    def load(self,candidate):self.calls.append('load')
    def migrate(self,env):
        self.calls.append('migrate')
        with closing(sqlite3.connect(Path(env['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3')) as db,db:
            db.execute('create table if not exists new_metadata(id integer primary key)')
            if self.fail=='migration':db.execute("update decisions set result='CORRUPTED' where id=1")
        if self.fail=='migration':raise ValueError('Controlled migration failure')
    def prepare_data(self,path):
        for name in ('static','upload-tmp'):(Path(path)/name).mkdir(exist_ok=True)
    def static_and_check(self,env):self.calls.append('static-check')
    def start_private(self,env):self.calls.append('private');self.running=env['ISURVIX_RELEASE_ID'];self.public=False
    def private_health(self,env):
        self.calls.append('private-health')
        if self.fail=='private-health' and env['ISURVIX_RELEASE_ID']==HEAD:raise ValueError('Controlled candidate private readiness failure')
    def open_public(self,env):
        self.calls.append('open-public');self.public=True;self.running=env['ISURVIX_RELEASE_ID']
        if self.fail=='late-health':
            with closing(sqlite3.connect(Path(env['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3')) as db,db:db.execute("insert into decisions values (2,'HUMAN_ACCEPTED_AFTER_OPEN')")
    def public_health(self,env):
        self.calls.append('public-health')
        if self.fail=='late-health' and env['ISURVIX_RELEASE_ID']==HEAD:raise ValueError('Controlled candidate external confirmation failure')
        if self.fail=='late-sqlite' and env['ISURVIX_RELEASE_ID']==HEAD:
            with closing(sqlite3.connect(Path(env['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3')) as db:db.execute('select nonexistent_health_column from decisions').fetchall()
        if self.running!=env['ISURVIX_RELEASE_ID'] or not self.public:raise ValueError('Actual fixture runtime does not match')
    def running_health(self,env):return self.public_health(env)


class SavedDataHostingerDeliveryTests(SimpleTestCase):
    def setUp(self):
        self.delivery=module();parent=ROOT/'.local/test-fixtures';parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='hostinger-delivery-',dir=parent);self.root=Path(self.temp.name)
        self.data=self.root/'original-data';(self.data/'media').mkdir(parents=True)
        with closing(sqlite3.connect(self.data/'database.sqlite3')) as db,db:
            db.execute('create table decisions(id integer primary key,result text)');db.execute("insert into decisions values(1,'HUMAN_APPROVED')")
            db.execute('create table django_migrations(id integer primary key,app text,name text)');db.execute("insert into django_migrations values(1,'core','0059_task_explorer_indexes')")
        (self.data/'media/original.jpg').write_bytes(b'unchanged-photo-original')
        self.env={'STAGING_HOST':'app.isurvix.com','ISURVIX_RELEASE_ID':OLD,'ISURVIX_APP_IMAGE':'sha256:'+'3'*64,'ISURVIX_NGINX_IMAGE':'sha256:'+'4'*64,'ISURVIX_DATA_DIRECTORY':str(self.data),'ISURVIX_SECRET_FILE':str(self.root/'secret'),'ISURVIX_TLS_DIRECTORY':str(self.root/'tls'),'ISURVIX_NGINX_CONFIG':str(self.root/'nginx.conf')}
        self.environment=self.root/'staging.env';self.environment.write_text(self.delivery.render_env(self.env))
        self.work=self.root/'private-delivery';self.work.mkdir()
        self.host=FixtureHost(self.delivery);self.host.running=OLD;self.host.public=True
        self.engine=self.delivery.Engine(self.work,self.environment,self.host)
        self.candidate={'pr':34,'head_sha':HEAD,'merge_sha':MERGE,'approval':'owner_merge','manifest_sha256':'e'*64,'images':IMAGES,'supported_from':[OLD],'package':str(self.root/'verified-package'),'artifact_id':100,'artifact_sha256':'f'*64}
    def tearDown(self):self.temp.cleanup()
    def rows(self,path):
        with closing(sqlite3.connect(Path(path)/'database.sqlite3')) as db:return db.execute('select * from decisions order by id').fetchall()
    def active(self):return json.loads((self.work/'active.json').read_text())
    def test_update_migrates_new_target_and_preserves_original_evidence_decisions(self):
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['release'],HEAD)
        current=self.delivery.read_env(self.environment);target=Path(current['ISURVIX_DATA_DIRECTORY'])
        self.assertNotEqual(target,self.data);self.assertEqual(self.rows(target),[(1,'HUMAN_APPROVED')]);self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')])
        self.assertEqual((target/'media/original.jpg').read_bytes(),b'unchanged-photo-original')
        self.assertLess(self.host.calls.index('private-health'),self.host.calls.index('open-public'))
        self.assertEqual(current['ISURVIX_RELEASE_ID'],HEAD)
        self.assertNotIn(MERGE,self.environment.read_text())
    def test_duplicate_replay_checks_actual_runtime_without_remigrating(self):
        self.engine.run(self.candidate);count=self.host.calls.count('migrate')
        replay=self.engine.run(self.candidate)
        self.assertEqual(replay['status'],'already_running')
        self.assertEqual(replay['source_release'],OLD);self.assertEqual(replay['core_schema'],'0059_task_explorer_indexes')
        self.assertEqual(replay['merge_sha'],MERGE);self.assertEqual(replay['artifact_id'],100)
        self.assertEqual(replay['artifact_sha256'],'f'*64);self.assertEqual(replay['images'],IMAGES)
        self.assertEqual(self.host.calls.count('migrate'),count)
        self.host.running=OLD
        with self.assertRaises(ValueError):self.engine.run(self.candidate)
        self.assertEqual(self.host.calls.count('migrate'),count)
    def test_failed_migration_rolls_back_into_another_new_verified_data_target(self):
        self.host.fail='migration';result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(self.active().get('failure_phase'),'migrating')
        self.assertEqual(self.active().get('failure_type'),'ValueError')
        self.assertNotIn('Controlled migration failure',json.dumps(self.active()))
        current=self.delivery.read_env(self.environment);restored=Path(current['ISURVIX_DATA_DIRECTORY'])
        self.assertNotEqual(restored,self.data);self.assertEqual(current['ISURVIX_RELEASE_ID'],OLD)
        self.assertEqual(self.rows(restored),[(1,'HUMAN_APPROVED')]);self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')])
        failed=Path(self.active()['target_env']['ISURVIX_DATA_DIRECTORY'])
        self.assertEqual(self.rows(failed),[(1,'CORRUPTED')]);self.assertTrue(failed.exists())
    def test_private_health_failure_rolls_back_but_never_opens_candidate_publicly(self):
        self.host.fail='private-health';result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'rolled_back');self.assertEqual(self.host.running,OLD)
        self.assertEqual(self.rows(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED')])
    def test_late_failure_freezes_new_accepted_records_without_rewinding(self):
        self.host.fail='late-health';result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'operator_recovery_required')
        current=self.delivery.read_env(self.environment)
        self.assertEqual(current['ISURVIX_RELEASE_ID'],HEAD)
        self.assertEqual(self.rows(current['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED'),(2,'HUMAN_ACCEPTED_AFTER_OPEN')])
        self.assertFalse(self.host.public)
        with self.assertRaises(ValueError):self.engine.run(self.candidate)
        self.assertEqual(self.rows(current['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED'),(2,'HUMAN_ACCEPTED_AFTER_OPEN')])
    def test_interruption_before_public_opening_recovers_durably_without_repeating_migration(self):
        def interrupt(phase,state):
            if phase=='migrating':raise KeyboardInterrupt('Synthetic interruption')
        self.engine.hook=interrupt
        with self.assertRaises(KeyboardInterrupt):self.engine.run(self.candidate)
        self.engine.hook=None
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'recovered')
        self.assertEqual(self.host.calls.count('migrate'),0)
        self.assertEqual(self.rows(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED')])
    def test_interruption_at_public_intent_requires_operator_and_keeps_target(self):
        def interrupt(phase,state):
            if phase=='public_opening':raise KeyboardInterrupt('Synthetic interruption')
        self.engine.hook=interrupt
        with self.assertRaises(KeyboardInterrupt):self.engine.run(self.candidate)
        self.engine.hook=None
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'operator_recovery_required')
        current=self.delivery.read_env(self.environment);self.assertEqual(current['ISURVIX_RELEASE_ID'],HEAD)
        self.assertEqual(self.rows(current['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED')])
    def test_unproven_source_upgrade_and_concurrent_delivery_are_rejected(self):
        self.candidate['supported_from']=[MERGE]
        with self.assertRaises(ValueError):self.engine.run(self.candidate)
        self.assertNotIn('stop',self.host.calls)
        self.candidate['supported_from']=[OLD]
        with self.delivery.lock(self.work):
            with self.assertRaises(ValueError):self.engine.run(self.candidate)
    def test_bad_archive_is_rejected_before_any_extraction(self):
        archive=self.root/'bad.zip'
        with ZipFile(archive,'w') as z:z.writestr('../outside.txt',b'forbidden')
        with self.assertRaises(ValueError):self.delivery.safe_extract(archive,self.root/'extracted')
        self.assertFalse((self.root/'outside.txt').exists());self.assertFalse((self.root/'extracted').exists())
    def test_bad_digest_and_case_duplicate_archive_cannot_be_accepted(self):
        archive=self.root/'bad.zip'
        with ZipFile(archive,'w') as z:z.writestr('safe.txt',b'a');z.writestr('SAFE.txt',b'b')
        with self.assertRaises(ValueError):self.delivery.safe_extract(archive,self.root/'extracted')
        with self.assertRaises(ValueError):self.delivery.verify_download(archive,archive.stat().st_size,'0'*64)
    def test_corrupt_archive_fails_with_controlled_error_before_target_creation(self):
        archive=self.root/'corrupt.zip';archive.write_bytes(b'not a ZIP file')
        with self.assertRaises(ValueError):self.delivery.safe_extract(archive,self.root/'extracted')
        self.assertFalse((self.root/'extracted').exists())
    def test_transaction_journal_contains_no_request_token(self):
        self.engine.run(self.candidate)
        text=''.join(p.read_text() for p in self.work.rglob('*.json'))
        self.assertNotIn('github_token',text);self.assertNotIn('fixture-token',text)
    def test_authority_revocation_before_publication_rolls_back_without_opening_candidate(self):
        self.engine.authority_check=lambda:(_ for _ in ()).throw(ValueError('Controlled stale branch or revoked approval'))
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'rolled_back');self.assertEqual(self.host.running,OLD)
        self.assertEqual(self.rows(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED')])
    def test_actual_candidate_sqlite_corruption_before_publication_rolls_back(self):
        original=self.host.static_and_check
        def corrupt(env):
            original(env)
            if env['ISURVIX_RELEASE_ID']==HEAD:(Path(env['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3').write_bytes(b'SYNTHETIC corrupt candidate database')
        self.host.static_and_check=corrupt
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'rolled_back');self.assertEqual(result['release'],OLD)
        self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')])
        self.assertEqual(self.rows(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED')])
        self.assertEqual((self.data/'media/original.jpg').read_bytes(),b'unchanged-photo-original')
    def test_actual_late_sqlite_error_freezes_and_preserves_new_human_rows(self):
        self.host.fail='late-sqlite'
        original_open=self.host.open_public
        def open_and_write(env):
            original_open(env)
            if env['ISURVIX_RELEASE_ID']==HEAD:
                with closing(sqlite3.connect(Path(env['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3')) as db,db:db.execute("insert into decisions values(2,'HUMAN_ACCEPTED_AFTER_OPEN')")
        self.host.open_public=open_and_write
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'operator_recovery_required');self.assertFalse(self.host.public)
        self.assertEqual(self.rows(self.delivery.read_env(self.environment)['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED'),(2,'HUMAN_ACCEPTED_AFTER_OPEN')])
        self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')])
        current=self.delivery.read_env(self.environment)
        with self.assertRaisesRegex(ValueError,'operator_recovery_required'):self.engine.run(self.candidate)
        self.assertEqual(self.delivery.read_env(self.environment),current)
        self.assertEqual(self.rows(current['ISURVIX_DATA_DIRECTORY']),[(1,'HUMAN_APPROVED'),(2,'HUMAN_ACCEPTED_AFTER_OPEN')])
    def test_sqlite_failure_while_forming_completed_receipt_never_rewinds(self):
        def corrupt_receipt(phase,state):
            if phase=='completed':(Path(state['target_env']['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3').write_bytes(b'SYNTHETIC corrupt after public opening')
        self.engine.hook=corrupt_receipt
        result=self.engine.run(self.candidate)
        self.assertEqual(result['status'],'operator_recovery_required');self.assertIsNone(result['core_schema']);self.assertFalse(self.host.public)
        current=self.delivery.read_env(self.environment)
        self.assertEqual(current['ISURVIX_RELEASE_ID'],HEAD)
        self.assertEqual((Path(current['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3').read_bytes(),b'SYNTHETIC corrupt after public opening')
        self.assertEqual(self.rows(self.data),[(1,'HUMAN_APPROVED')])
