"""Disposable CI-only REAL Docker Host/Engine rehearsal; never a VPS installer.

Uses images/packages already built and proven by the existing upgrade drill.
Only synthetic data is initialized; no GitHub token or native model is used.
"""
import argparse
from contextlib import closing
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, Request, HTTPCookieProcessor, HTTPSHandler, ProxyHandler
import ssl
import uuid

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reviewed_delivery_controller',HERE/'controller.py')
delivery=importlib.util.module_from_spec(spec);spec.loader.exec_module(delivery)


def disposable(work,*,environ=None,uid=None,platform=None):
    environ=os.environ if environ is None else environ
    uid=(os.geteuid() if hasattr(os,'geteuid') else -1) if uid is None else uid
    platform=os.name if platform is None else platform
    if platform!='posix' or uid!=0 or environ.get('GITHUB_ACTIONS')!='true' or environ.get('ISURVIX_DISPOSABLE_REHEARSAL')!='yes' or not environ.get('RUNNER_TEMP'):raise ValueError('Explicit disposable GitHub Linux-root rehearsal required.')
    work=delivery.consumer._no_links(work);parent=delivery.consumer._no_links(environ['RUNNER_TEMP'])
    if work.exists() or not work.is_absolute() or work==parent or not work.is_relative_to(parent):raise ValueError('Use a NEW private work path beneath RUNNER_TEMP.')


def upgrade_proof(proof,source,target,images,manifest_sha256):
    if proof.get('release')!=target or source not in proof.get('supported_from',[]) or proof.get('images')!=images or proof.get('manifest_sha256')!=manifest_sha256 or any(proof.get(key) is not True for key in ('upgrade_recovery_verified','caught_failure_rolled_back','interrupted_process_recovered')):raise ValueError('The existing real upgrade/recovery proof does not bind these packages.')


def command(*args):
    result=subprocess.run(list(map(str,args)),capture_output=True,check=False,timeout=120)
    if result.returncode:raise ValueError('Disposable fixture command failed; private output suppressed.')
    return result.stdout


def free_ports():
    listeners=[]
    try:
        for address,port in [('0.0.0.0',443),('127.0.0.1',8080),('127.0.0.1',8443)]:
            sock=socket.socket();listeners.append(sock);sock.bind((address,port))
    except OSError:raise ValueError('Required rehearsal ports are occupied. No service was changed.') from None
    finally:
        for sock in listeners:sock.close()


def schema(data):
    with closing(sqlite3.connect((Path(data)/'database.sqlite3').absolute().as_uri()+'?mode=ro',uri=True)) as db:
        row=db.execute("select name from django_migrations where app='core' order by name desc limit 1").fetchone()
        return row[0] if row else None


def client_checks(password,reference,release):
    base='https://'+delivery.HOST
    def session(username=None):
        jar=http.cookiejar.CookieJar()
        opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(jar),HTTPSHandler(context=ssl.create_default_context()),delivery._NoRedirect())
        if username:
            with opener.open(base+'/login/',timeout=15) as response:
                if response.status!=200:raise ValueError('Fixture login page failed.')
            token=next(cookie.value for cookie in jar if cookie.name=='csrftoken')
            request=Request(base+'/login/',data=urlencode({'username':username,'password':password,'csrfmiddlewaretoken':token}).encode(),headers={'Referer':base+'/login/'})
            try:
                response=opener.open(request,timeout=15);response.close();raise ValueError('Fixture login did not redirect.')
            except HTTPError as response:
                if response.code!=302:raise ValueError('Fixture login rejected.') from None
        return opener
    owner=session('synthetic_owner');engineer=session('synthetic_retained_engineer');anonymous=session()
    url=base+'/local/photos/{checklist_id}/evidence/{photo_id}/original/'.format(**reference)
    with engineer.open(url,timeout=15) as response:
        raw=response.read(1024*1024)
        if response.status!=200 or hashlib.sha256(raw).hexdigest()!=reference['sha256']:raise ValueError('Retained engineer original bytes differ.')
    for principal,allowed in [(owner,{403}),(anonymous,{302,404})]:
        try:
            response=principal.open(url,timeout=15);status=response.status;response.close()
        except HTTPError as response:status=response.code
        if status not in allowed:raise ValueError('Actual retained-evidence access restriction failed.')
    with engineer.open(base+'/ops/health/ready/',timeout=15) as response:delivery._health_body(response.read(16384),release)
    return {'actual_https':True,'engineer_original_hash_verified':True,'owner_operational_read_denied':True,'anonymous_original_denied':True,'physical_device_tested':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('work','source-package','target-package'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('source-release','target-release'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv);stage='disposable-guard';host=None;hosts_before=None;ssl_before=os.environ.get('SSL_CERT_FILE');work=args.work;created=False
    result={'format':'isurvix-hostinger-docker-rehearsal-v1','status':'failed','synthetic_only':True,'owner_release_approved':False,'native_ai_tested':False,'live_customer_server_changed':False}
    try:
        disposable(work);free_ports()
        delivery._sha(args.source_release);delivery._sha(args.target_release)
        if args.source_release==args.target_release:raise ValueError('A restart is not an upgrade test.')
        source=delivery.consumer.verify_package(args.source_package);target=delivery.consumer.verify_package(args.target_package)
        if source['release_id']!=args.source_release or target['release_id']!=args.target_release:raise ValueError('Package/source identity differs.')
        manifest_hash=delivery.consumer._digest(args.target_package/'manifest.json')['sha256']
        proof=delivery.consumer._json(args.target_package.parent/'update-rehearsal/upgrade-verification.json')
        upgrade_proof(proof,args.source_release,args.target_release,target['images'],manifest_hash)
        work.mkdir(mode=0o700);created=True;runtime=work/'runtime';runtime.mkdir(mode=0o700)
        journal=work/'journal';journal.mkdir(mode=0o700);data=work/'original-synthetic-data';data.mkdir(mode=0o700);(data/'media').mkdir(mode=0o700)
        tls=work/'tls';tls.mkdir(mode=0o755)
        config=tls/'fixture.cnf';config.write_text('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=v3\n[dn]\nCN=app.isurvix.com\n[v3]\nsubjectAltName=DNS:app.isurvix.com\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,digitalSignature,keyEncipherment,keyCertSign,cRLSign\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n')
        stage='fixture-tls';command('openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-config',config,'-keyout',tls/'privkey.pem','-out',tls/'fullchain.pem')
        os.chown(tls/'privkey.pem',101,101);(tls/'privkey.pem').chmod(0o400);(tls/'fullchain.pem').chmod(0o444)
        secret=work/'django-secret';secret.write_text(secrets.token_urlsafe(64));os.chown(secret,10001,10001);secret.chmod(0o400)
        password=secrets.token_urlsafe(32);password_file=work/'fixture-password';password_file.write_text(password);os.chown(password_file,10001,10001);password_file.chmod(0o400)
        wrapper=runtime/'ifield_settings.py';shutil.copyfile(HERE/'runtime/ifield_settings.py',wrapper);wrapper.chmod(0o644)
        override=runtime/'public.override.json';override.write_text(json.dumps({'services':{'web':{'environment':{'DJANGO_CSRF_TRUSTED_ORIGINS':'https://app.isurvix.com,https://app.isurvix.com:8443','DJANGO_SETTINGS_MODULE':'ifield_settings','PYTHONPATH':'/run/isurvix-config'},'volumes':[str(wrapper)+':/run/isurvix-config/ifield_settings.py:ro']},'proxy':{'ports':['0.0.0.0:443:8443']}}}))
        trusted_staging=delivery._module(HERE.parent/'staging.py','reviewed_ci_staging')
        nginx=runtime/'nginx.conf';nginx.write_text(trusted_staging.render_nginx(host=delivery.HOST,upstream='web:8000',static_root='/data/static',certificate='/tls/fullchain.pem',key='/tls/privkey.pem',http_port=8080,https_port=8443));nginx.chmod(0o644)
        environment=runtime/'staging.env';values={'STAGING_HOST':delivery.HOST,'ISURVIX_RELEASE_ID':args.source_release,'ISURVIX_APP_IMAGE':source['images']['app'],'ISURVIX_NGINX_IMAGE':source['images']['nginx'],'ISURVIX_DATA_DIRECTORY':str(data),'ISURVIX_SECRET_FILE':str(secret),'ISURVIX_TLS_DIRECTORY':str(tls),'ISURVIX_NGINX_CONFIG':str(nginx)}
        delivery.atomic(environment,delivery.render_env(values).encode())
        policy={'environment_file':str(environment),'project':'delivery-rehearsal-'+uuid.uuid4().hex[:12],'compose_files':[str(HERE.parent/'compose.yaml'),str(override)],'root':str(journal)}
        host=delivery.Host(policy);host.prepare_data(data)
        stage='source-bootstrap';delivery.consumer.load_images(args.source_package,acknowledge_draft=True)
        host.dc('run','--rm','--no-deps','--pull','never','-e','ISURVIX_INITIALIZE_DATABASE=yes','web','python','manage.py','migrate','--noinput');(data/'database.sqlite3').chmod(0o600);host.static_and_check(values)
        seed_script="from pathlib import Path;from django.contrib.auth import get_user_model;U=get_user_model();assert U.objects.count()==0;U.objects.create_superuser('synthetic_owner','owner@example.test',Path('/run/fixture-password').read_text());import sys,json;sys.path.insert(0,'/app/deploy/customer');import upgrade_fixture;print(json.dumps(upgrade_fixture.seed(engineer_password=Path('/run/fixture-password').read_text())))"
        raw=host.dc('run','--rm','--no-deps','--pull','never','-e','ISURVIX_DISPOSABLE_REHEARSAL=yes','-v',str(password_file)+':/run/fixture-password:ro','web','python','manage.py','shell','-c',seed_script)
        seeded=json.loads(raw.decode().splitlines()[-1])
        if seeded.get('synthetic_only') is not True or seeded.get('engineering_approvals_created')!=0 or seeded.get('native_ai_calls')!=0:raise ValueError('The pristine synthetic seed was not verified.')
        hosts=Path('/etc/hosts');hosts_before=hosts.read_bytes();hosts.write_bytes(hosts_before+b'\n127.0.0.1 app.isurvix.com # isolated-delivery-rehearsal\n')
        if {row[4][0] for row in socket.getaddrinfo(delivery.HOST,443,family=socket.AF_INET)}!={'127.0.0.1'}:raise ValueError('Rehearsal DNS is not exclusively loopback.')
        os.environ['SSL_CERT_FILE']=str(tls/'fullchain.pem')
        stage='source-actual-health';host.preflight(values);host.start_private(values);host.private_health(values);host.open_public(values);host.public_health(values)
        before=delivery.retention.snapshot(data/'database.sqlite3');media_before={name:delivery.consumer._digest(path) for name,path in delivery.consumer._files(data/'media').items()}
        candidate={'pr':999999,'head_sha':args.target_release,'merge_sha':args.target_release,'approval':'synthetic_rehearsal_only_not_github_approval','manifest_sha256':manifest_hash,'images':target['images'],'supported_from':[args.source_release],'package':str(args.target_package),'artifact_id':0,'artifact_sha256':delivery.consumer._digest(args.target_package/'images/server-images.tar')['sha256']}
        class MigrationFailure(delivery.Host):
            def migrate(self,env):super().migrate(env);raise ValueError('Explicit disposable failure after actual migration.')
        stage='actual-failed-migration-recovery';failed=delivery.Engine(journal,environment,MigrationFailure(policy)).run(candidate)
        if failed['status']!='rolled_back' or failed['release']!=args.source_release:raise ValueError('Actual early failure did not recover original version.')
        recovered=delivery.read_env(environment);delivery.retention.assert_retained(before,Path(recovered['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3');delivery.retention.assert_retained(before,data/'database.sqlite3')
        stage='actual-successful-host-update';engine=delivery.Engine(journal,environment,host);completed=engine.run(candidate)
        if completed['status']!='completed' or completed['release']!=args.target_release:raise ValueError('Actual Docker update failed.')
        replay=engine.run(candidate)
        if replay['status']!='already_running' or replay['source_release']!=args.source_release:raise ValueError('Actual Docker replay did not verify the running target.')
        active=delivery.read_env(environment);active_data=Path(active['ISURVIX_DATA_DIRECTORY']);retained=delivery.retention.assert_retained(before,active_data/'database.sqlite3')
        if {name:delivery.consumer._digest(path) for name,path in delivery.consumer._files(active_data/'media').items()}!=media_before:raise ValueError('Actual Host evidence hashes changed.')
        stage='actual-authenticated-user-read';clients=client_checks(password,seeded['first_photo'],args.target_release)
        result.update(status='passed',source_release=args.source_release,target_release=args.target_release,images=target['images'],manifest_sha256=manifest_hash,source_schema=schema(data),target_schema=schema(active_data),actual_docker_host_tested=True,actual_failed_migration_recovered=True,actual_private_tls_and_public_https_verified=True,actual_running_replay_verified=True,source_records_unchanged=True,retained_data=retained,evidence_files=len(media_before),evidence_hashes_identical=True,authenticated_client=clients,git_authority_tested_in_this_drill=False,github_artifact_download_tested_in_this_drill=False,runtime_image_pulls=0)
    except Exception as error:
        result.update(status='failed',stage=stage,error_type=type(error).__name__,error='Controlled disposable rehearsal failure; no private output exported.')
    finally:
        cleanup=True
        if host:
            try:host.dc('down','--remove-orphans')
            except Exception:cleanup=False
        if hosts_before is not None:
            try:Path('/etc/hosts').write_bytes(hosts_before)
            except Exception:cleanup=False
        if ssl_before is None:os.environ.pop('SSL_CERT_FILE',None)
        else:os.environ['SSL_CERT_FILE']=ssl_before
        result['cleanup_completed']=cleanup
        if not cleanup:result['status']='failed';result['error']='Disposable cleanup needs operator inspection.'
        if created:
            output=work/'verification.json';output.write_text(json.dumps(result,indent=2)+'\n');output.chmod(0o644);work.chmod(0o711)
        print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='passed' else 2


if __name__=='__main__':raise SystemExit(main())
