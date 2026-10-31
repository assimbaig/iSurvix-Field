"""Production configuration and release tooling without operational data/network."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile

from django.test import SimpleTestCase

ROOT=Path(__file__).resolve().parents[2]


class StagingConfigurationTests(SimpleTestCase):
    def setUp(self):
        base=ROOT/'.local/test-runs';base.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='staging-config-',dir=base)
        self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)
        for part in ['data/media','data/static','data/upload-tmp']:(self.path/part).mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.path/'data/database.sqlite3')
        try:
            db.execute('create table preservation_marker(value text)')
            db.execute("insert into preservation_marker values ('original disposable fixture')")
            db.commit()
        finally:db.close()
        self.secret=self.path/'secret';self.secret.write_text('isolated-staging-test-key-'*4,encoding='utf-8')
        self.release=self.path/'release';self.release.write_text('a'*40,encoding='utf-8')
        self.env={k:v for k,v in os.environ.items() if not k.startswith(('DJANGO_','ISURVIX_'))}
        self.env.update(DJANGO_SECRET_KEY_FILE=str(self.secret),DJANGO_ALLOWED_HOSTS='staging.example.test',
                        DJANGO_CSRF_TRUSTED_ORIGINS='https://staging.example.test',
                        ISURVIX_DATA_ROOT=str(self.path/'data'),ISURVIX_RELEASE_ID='a'*40,
                        ISURVIX_RELEASE_FILE=str(self.release),DEBUG='False',PYTHONPATH=str(ROOT/'backend'))

    def run_config(self, **overrides):
        env={**self.env,**overrides}
        code="import json; from checklist import settings_staging as s; print(json.dumps({'debug':s.DEBUG,'database':str(s.DATABASES['default']['NAME']),'media':str(s.MEDIA_ROOT),'local_ai':s.LOCAL_AI_ENABLED,'release':s.ISURVIX_RELEASE_ID,'transaction':s.DATABASES['default']['OPTIONS']['transaction_mode'],'cookie':s.SESSION_COOKIE_SECURE,'static':str(s.STATIC_ROOT)}))"
        return subprocess.run([sys.executable,'-c',code],cwd=ROOT/'backend',env=env,text=True,capture_output=True)

    def test_valid_settings_separate_persistent_data_disable_inference_and_do_not_write(self):
        before=set(self.path.rglob('*'));result=self.run_config()
        self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(result.stdout)
        self.assertEqual(Path(actual['database']),self.path/'data/database.sqlite3')
        self.assertEqual(Path(actual['media']),self.path/'data/media')
        self.assertFalse(actual['debug']);self.assertFalse(actual['local_ai']);self.assertTrue(actual['cookie'])
        self.assertEqual(actual['transaction'],'IMMEDIATE')
        self.assertEqual(before,set(self.path.rglob('*')))

    def test_secrets_are_required_and_ambiguous_sources_rejected(self):
        self.assertNotEqual(self.run_config(DJANGO_SECRET_KEY_FILE='').returncode,0)
        self.assertNotEqual(self.run_config(DJANGO_SECRET_KEY='b'*60).returncode,0)

    def test_short_or_development_secret_rejected_without_echo(self):
        self.secret.write_text('django-insecure-do-not-use',encoding='utf-8')
        result=self.run_config();self.assertNotEqual(result.returncode,0)
        self.assertNotIn('django-insecure-do-not-use',result.stderr)

    def test_wildcard_loopback_and_url_hosts_rejected(self):
        for value in ['*','localhost','127.0.0.1','https://staging.example.test','staging.example.test,*']:
            with self.subTest(value=value):self.assertNotEqual(self.run_config(DJANGO_ALLOWED_HOSTS=value).returncode,0)

    def test_origin_requires_https_and_bound_host(self):
        for value in ['', 'http://staging.example.test','https://foreign.example.test','https://staging.example.test/']:
            with self.subTest(value=value):self.assertNotEqual(self.run_config(DJANGO_CSRF_TRUSTED_ORIGINS=value).returncode,0)

    def test_debug_native_ai_and_code_tree_data_rejected(self):
        for values in [{'DEBUG':'True'},{'ISURVIX_LOCAL_AI_ENABLED':'True'},{'ISURVIX_DATA_ROOT':str(ROOT/'backend')}]:
            with self.subTest(values=values):self.assertNotEqual(self.run_config(**values).returncode,0)

    def test_release_is_full_commit_and_matches_baked_identity(self):
        for value in ['', 'latest', 'abc123', 'b'*40]:
            with self.subTest(value=value):self.assertNotEqual(self.run_config(ISURVIX_RELEASE_ID=value).returncode,0)

    def test_missing_database_never_becomes_an_empty_web_install_without_explicit_bootstrap(self):
        (self.path/'data/database.sqlite3').unlink()
        self.assertNotEqual(self.run_config().returncode,0)
        self.assertEqual(self.run_config(ISURVIX_INITIALIZE_DATABASE='yes').returncode,0)
        self.assertFalse((self.path/'data/database.sqlite3').exists())

    def test_readonly_production_management_checks_have_no_deployment_warnings(self):
        env={**self.env,'DJANGO_SETTINGS_MODULE':'checklist.settings_staging'}
        before=hashlib.sha256((self.path/'data/database.sqlite3').read_bytes()).hexdigest()
        result=subprocess.run([sys.executable,'manage.py','check','--deploy','--fail-level','WARNING'],
                              cwd=ROOT/'backend',env=env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(before,hashlib.sha256((self.path/'data/database.sqlite3').read_bytes()).hexdigest())

    def test_existing_deployment_helper_accepts_private_file_secret_and_preserves_database(self):
        bash='C:/Program Files/Git/bin/bash.exe' if os.name=='nt' else '/bin/bash'
        env={**self.env,'DJANGO_SETTINGS_MODULE':'checklist.settings_staging',
             'DJANGO_SECRET_KEY_FILE':self.secret.as_posix(),'ISURVIX_PYTHON':Path(sys.executable).as_posix()}
        before=hashlib.sha256((self.path/'data/database.sqlite3').read_bytes()).hexdigest()
        result=subprocess.run([bash,str(ROOT/'backend/deploy.sh'),'--check'],cwd=ROOT,env=env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('No database migration',result.stdout)
        self.assertNotIn(self.secret.read_text(),result.stdout+result.stderr)
        self.assertEqual(before,hashlib.sha256((self.path/'data/database.sqlite3').read_bytes()).hexdigest())


class StagingReleaseToolTests(SimpleTestCase):
    def tool(self):
        spec=importlib.util.spec_from_file_location('staging_release_tool',ROOT/'deploy/staging.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_nginx_render_keeps_all_media_private_and_forwards_real_scheme(self):
        config=self.tool().render_nginx(host='staging.example.test',upstream='127.0.0.1:8951',
            static_root='F:/isolated/static',certificate='F:/isolated/cert.pem',key='F:/isolated/key.pem',
            http_port=8950,https_port=8952,listen_address='127.0.0.1')
        self.assertIn('location = /media { return 404; }',config)
        self.assertIn('location ^~ /media/ { return 404; }',config)
        self.assertNotIn('alias "F:/isolated/media',config)
        self.assertIn('proxy_set_header X-Forwarded-Proto $scheme;',config)
        self.assertIn('proxy_pass http://127.0.0.1:8951;',config)
        self.assertNotIn('$request_uri',config.split('log_format')[1].split(';')[0])

    def test_nginx_render_rejects_directive_injection(self):
        for host in ['staging.example.test; include /secret;', 'staging.example.test\nserver {}']:
            with self.subTest(host=host),self.assertRaises(ValueError):
                self.tool().render_nginx(host=host,upstream='web:8000',static_root='/data/static',certificate='/tls/fullchain.pem',key='/tls/privkey.pem')

    def test_release_validation_refuses_mutable_image_tags(self):
        with self.assertRaises(ValueError):self.tool().image_reference('nginx:latest')
        value='nginx:stable-alpine@sha256:'+'a'*64
        self.assertEqual(self.tool().image_reference(value),value)

    def test_prepare_exports_only_clean_reviewed_commit_and_bakes_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local/test-runs',prefix='release-export-') as temporary:
            folder=Path(temporary);repo=folder/'repo';repo.mkdir()
            def run(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
            run('init','-q');run('config','user.name','Synthetic release test');run('config','user.email','fixture@example.test')
            (repo/'.gitignore').write_text('.private/\n');(repo/'source.txt').write_text('reviewed source')
            run('add','.');run('commit','-qm','synthetic initial source')
            private=repo/'.private';private.mkdir();(private/'secret').write_text('never copied')
            commit=run('rev-parse','HEAD');target=folder/'context'
            result=self.tool().prepare_release(repo,target,commit)
            self.assertEqual(result['release_id'],commit)
            self.assertEqual((target/'RELEASE').read_text(),commit+'\n')
            self.assertEqual((target/'source.txt').read_text(),'reviewed source')
            self.assertFalse((target/'.private').exists());self.assertFalse((target/'.git').exists())
            (repo/'source.txt').write_text('unreviewed modification')
            with self.assertRaises(ValueError):self.tool().prepare_release(repo,folder/'other',commit)
            with self.assertRaises(ValueError):self.tool().prepare_release(repo,target,commit)

    def test_compose_has_no_host_database_web_or_ollama_port(self):
        text=(ROOT/'deploy/compose.yaml').read_text()
        self.assertNotIn('11434:',text);self.assertNotIn('5432:',text);self.assertNotIn('8000:8000',text)
        self.assertIn('127.0.0.1:8443:8443',text)
        self.assertIn('read_only: true',text)
        self.assertIn('restart: unless-stopped',text)

    def test_config_validation_rejects_modified_private_media_proxy_policy(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.local/test-runs',prefix='release-config-') as temporary:
            folder=Path(temporary);data=folder/'data';tls=folder/'tls'
            for part in ['media','static','upload-tmp']:(data/part).mkdir(parents=True,exist_ok=True)
            (data/'database.sqlite3').touch();tls.mkdir()
            for name in ['fullchain.pem','privkey.pem']:(tls/name).write_text('synthetic path-validation fixture only')
            secret=folder/'secret';secret.write_text('synthetic secret path fixture')
            config=folder/'nginx.conf';tool=self.tool()
            expected=tool.render_nginx(host='staging.example.test',upstream='web:8000',static_root='/data/static',
                certificate='/tls/fullchain.pem',key='/tls/privkey.pem',http_port=8080,https_port=8443)
            config.write_text(expected)
            values={'STAGING_HOST':'staging.example.test','ISURVIX_RELEASE_ID':'a'*40,
                'ISURVIX_APP_IMAGE':'sha256:'+'b'*64,'ISURVIX_NGINX_IMAGE':'nginx:stable@sha256:'+'c'*64,
                'ISURVIX_DATA_DIRECTORY':str(data),'ISURVIX_SECRET_FILE':str(secret),
                'ISURVIX_TLS_DIRECTORY':str(tls),'ISURVIX_NGINX_CONFIG':str(config)}
            self.assertFalse(tool.validate_environment(values)['deployment_performed'])
            config.write_text(expected.replace('location ^~ /media/ { return 404; }','location /media/ { alias /data/media/; }'))
            with self.assertRaises(ValueError):tool.validate_environment(values)

    def test_direct_staging_constraints_satisfy_existing_backend_requirement_ranges(self):
        from packaging.requirements import Requirement
        original={r.name.lower():r for line in (ROOT/'backend/requirements.txt').read_text().splitlines()
                  if line.strip() and not line.lstrip().startswith('#') for r in [Requirement(line)]}
        pinned={r.name.lower():r for line in (ROOT/'deploy/requirements.staging.txt').read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#') for r in [Requirement(line)]}
        self.assertEqual(set(original),set(pinned))
        for name,requirement in pinned.items():
            spec=list(requirement.specifier);self.assertEqual(len(spec),1);self.assertEqual(spec[0].operator,'==')
            self.assertTrue(original[name].specifier.contains(spec[0].version),name)

    def test_compose_tmpfs_options_are_one_mount_per_service(self):
        import yaml
        config=yaml.safe_load((ROOT/'deploy/compose.yaml').read_text())
        for name in ['web','proxy']:
            mounts=config['services'][name]['tmpfs']
            self.assertEqual(len(mounts),1,name)
            self.assertTrue(mounts[0].startswith('/tmp:'),name)
            self.assertIn('size=',mounts[0])
