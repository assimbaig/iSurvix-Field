"""Trusted Hostinger release controller. No caller-selected commands or paths.

Installed code/policy are root-owned; the SSH account only submits bounded
PR-number/ephemeral-token JSON. Candidate code executes inside the existing
unprivileged application container, never as root on the host.
"""
from contextlib import contextmanager, closing, nullcontext
from datetime import datetime, timezone
import hashlib
from http.client import HTTPResponse
import io
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import ssl
import sqlite3
import stat
import subprocess
import sys
import time
import types
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
from zipfile import ZipFile, BadZipFile

HERE=Path(__file__).resolve().parent
REPOSITORY='assimbaig/iSurvix-Field'
BRANCH='feat/ai-settings-routing-20261031'
OWNER='assimbaig'
HOST='app.isurvix.com'
SHARED_WORKFLOW='.github/workflows/shared-release-candidate.yml'


def _module(path,name):
    value=types.ModuleType(name);value.__file__=str(path)
    exec(compile(Path(path).read_bytes(),str(path),'exec'),value.__dict__)
    return value


# Only separately installed trusted helpers, never imports from the candidate.
release_gate=_module(HERE.parent/'release_gate.py','trusted_delivery_gate')
consumer=_module(HERE.parent/'customer/customer.py','trusted_delivery_consumer')
backup=_module(HERE.parents[1]/'backend/core/operations_backup.py','trusted_delivery_backup')
retention=_module(HERE.parent/'customer/upgrade_fixture.py','trusted_delivery_retention')


class DeliveryError(ValueError):pass


def _sha(value,length=40):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{%d}'%length,value):raise DeliveryError('invalid_identity')
    return value


def _json(raw):
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise DeliveryError('duplicate_json_key')
            value[key]=item
        return value
    try:return json.loads(raw,object_pairs_hook=unique)
    except (UnicodeError,json.JSONDecodeError):raise DeliveryError('invalid_json') from None


def read_request(stream,*,body_timeout=10):
    if isinstance(stream,io.BytesIO):raw=stream.read(8193)
    else:
        if os.name!='posix' or not isinstance(body_timeout,(int,float)) or not 0<body_timeout<=10:raise DeliveryError('production_request_stream_requires_posix')
        try:descriptor=stream.fileno()
        except (OSError,ValueError,AttributeError):raise DeliveryError('request_stream_unavailable') from None
        deadline=time.monotonic()+body_timeout;buffer=bytearray()
        while len(buffer)<8193:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise DeliveryError('request_body_deadline')
            try:
                ready,_,_=select.select([descriptor],[],[],remaining)
                if not ready:raise DeliveryError('request_body_deadline')
                chunk=os.read(descriptor,min(4096,8193-len(buffer)))
            except OSError:raise DeliveryError('request_stream_unavailable') from None
            if not chunk:break
            buffer.extend(chunk)
        raw=bytes(buffer)
    if not raw or len(raw)>8192:raise DeliveryError('request_size')
    value=_json(raw)
    if not isinstance(value,dict) or set(value)!={'pr','github_token'} or type(value['pr']) is not int or not 1<=value['pr']<=999999:raise DeliveryError('request_shape')
    token=value['github_token']
    if not isinstance(token,str) or not 20<=len(token)<=512 or any(not 33<=ord(c)<=126 for c in token):raise DeliveryError('credential_unavailable')
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def storage_url(value):
    try:
        parts=urlsplit(value)
        if parts.scheme!='https' or parts.username or parts.password or parts.port not in (None,443) or not parts.hostname or not any(parts.hostname.endswith(suffix) for suffix in ('.blob.core.windows.net','.actions.githubusercontent.com','.artifacts.githubusercontent.com')) or any(ord(c)<33 for c in value):raise ValueError()
    except (ValueError,TypeError):raise DeliveryError('artifact_storage_destination') from None
    return value


class GitHub:
    def __init__(self,token):self.token=token
    def _request(self,path):
        if not path.startswith('/repos/'+REPOSITORY+'/') or any(c in path for c in '\r\n\\#'):raise DeliveryError('api_path')
        return Request('https://api.github.com'+path,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'iSurvix-guarded-host-delivery'})
    def get(self,path):
        try:
            with build_opener(_NoRedirect()).open(self._request(path),timeout=30) as response:
                raw=response.read(8*1024*1024+1)
                if len(raw)>8*1024*1024:raise DeliveryError('api_response_size')
                return _json(raw)
        except (HTTPError,URLError,OSError):raise DeliveryError('github_unavailable_or_credential_revoked') from None
    def pages(self,path,key=None):
        result=[]
        for page in range(1,11):
            data=self.get(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))
            rows=data.get(key) if key and isinstance(data,dict) else data
            if not isinstance(rows,list):raise DeliveryError('api_collection_shape')
            result.extend(rows)
            if len(rows)<100:return result
        raise DeliveryError('api_collection_limit')
    def download(self,artifact_id,target,size,digest):
        try:
            try:
                unexpected=build_opener(_NoRedirect()).open(self._request('/repos/'+REPOSITORY+'/actions/artifacts/'+str(artifact_id)+'/zip'),timeout=30)
                unexpected.close();raise DeliveryError('artifact_redirect_missing')
            except HTTPError as error:
                if error.code!=302:raise DeliveryError('artifact_download_authorization') from None
                signed=storage_url(error.headers.get('Location',''))
            start=time.monotonic();total=0
            # A fresh request with NO Authorization; the signed URL stays in RAM.
            with build_opener(_NoRedirect()).open(Request(signed,headers={'User-Agent':'iSurvix-guarded-host-delivery'}),timeout=45) as response,Path(target).open('xb') as stream:
                if response.status!=200:raise DeliveryError('artifact_storage_status')
                while chunk:=response.read(4*1024*1024):
                    total+=len(chunk)
                    if total>size or time.monotonic()-start>1200:raise DeliveryError('artifact_download_bounds')
                    stream.write(chunk)
                stream.flush();os.fsync(stream.fileno())
            verify_download(target,size,digest)
        except (HTTPError,URLError,OSError):raise DeliveryError('artifact_download_interrupted') from None


def authorize(client,number):
    prefix='/repos/'+REPOSITORY
    pr=client.get(prefix+'/pulls/'+str(number))
    try:
        if pr['number']!=number or pr['merged'] is not True or pr['state']!='closed' or not pr['merged_at'] or pr['head']['repo']['full_name']!=REPOSITORY or pr['base']['repo']['full_name']!=REPOSITORY or pr['base']['ref']!=BRANCH:raise DeliveryError('pr_not_authorized')
        head=_sha(pr['head']['sha']);merged=_sha(pr['merge_commit_sha'])
        if client.get(prefix+'/git/ref/heads/'+quote(BRANCH,safe=''))['object']['sha']!=merged:raise DeliveryError('branch_advanced')
        head_tree=_sha(client.get(prefix+'/git/commits/'+head)['tree']['sha'])
        if head_tree!=_sha(client.get(prefix+'/git/commits/'+merged)['tree']['sha']):raise DeliveryError('merge_tree_differs_require_rebase_ci')
        approval='owner_merge'
        if pr.get('merged_by',{}).get('login','').casefold()!=OWNER.casefold():
            reviews=[r for r in client.pages(prefix+'/pulls/'+str(number)+'/reviews') if r.get('user',{}).get('login','').casefold()==OWNER.casefold() and r.get('commit_id')==head]
            if not reviews or max(reviews,key=lambda r:r.get('id',0)).get('state')!='APPROVED':raise DeliveryError('exact_head_owner_approval_missing')
            approval='owner_review'
        return {'pr':number,'head_sha':head,'merge_sha':merged,'head_tree':head_tree,'approval':approval}
    except (KeyError,TypeError,AttributeError):raise DeliveryError('pr_metadata_shape') from None


def require_checks(client,head):
    rows=client.pages('/repos/'+REPOSITORY+'/actions/runs?head_sha='+_sha(head),key='workflow_runs')
    return release_gate.verified_runs(rows,head,REPOSITORY)


def verify_download(path,size,digest):
    if type(size) is not int or not 1<=size<=2*1024**3:raise DeliveryError('artifact_size')
    _sha(digest,64)
    actual=consumer._digest(consumer._no_links(path))
    if actual!={'size':size,'sha256':digest}:raise DeliveryError('artifact_digest')
    return actual


def safe_extract(path,target):
    try:return _extract_zip(path,target)
    except (BadZipFile,RuntimeError,NotImplementedError):raise DeliveryError('archive_invalid_or_unsupported') from None


def _extract_zip(path,target):
    target=consumer._no_links(target)
    if target.exists():raise DeliveryError('artifact_target_exists')
    with ZipFile(path) as archive:
        rows=archive.infolist();names=set();total=0
        if not 1<=len(rows)<=20000:raise DeliveryError('archive_count')
        for row in rows:
            name=row.filename.rstrip('/');consumer._relative(name)
            kind=stat.S_IFMT(row.external_attr>>16)
            if len(name)>512 or name.casefold() in names or kind not in (0,stat.S_IFREG,stat.S_IFDIR) or row.flag_bits&1:raise DeliveryError('archive_member')
            names.add(name.casefold());total+=row.file_size
            if row.file_size>6*1024**3 or total>8*1024**3:raise DeliveryError('archive_size')
        if archive.testzip() is not None:raise DeliveryError('archive_crc')
        if shutil.disk_usage(target.parent).free<total+512*1024**2:raise DeliveryError('archive_disk_reserve')
        target.mkdir(mode=0o700);archive.extractall(target)


def acquire(client,authority,root):
    root=consumer._no_links(root);root.mkdir(mode=0o700,parents=True,exist_ok=True)
    checks=require_checks(client,authority['head_sha'])
    runs=client.pages('/repos/'+REPOSITORY+'/actions/runs?head_sha='+authority['head_sha'],key='workflow_runs')
    shared={}
    for row in runs:
        if row.get('path')!=SHARED_WORKFLOW or row.get('head_sha')!=authority['head_sha'] or row.get('head_repository',{}).get('full_name')!=REPOSITORY:continue
        previous=shared.get(row['id'])
        if previous is None or row['run_attempt']>previous['run_attempt']:shared[row['id']]=row
    if not shared or any(r.get('status')!='completed' or r.get('conclusion')!='success' for r in shared.values()):raise DeliveryError('shared_producer_not_successful')
    producer=max(shared.values(),key=lambda r:(r['run_number'],r['run_attempt'],r['id']))
    artifacts=client.pages('/repos/'+REPOSITORY+'/actions/runs/'+str(producer['id'])+'/artifacts',key='artifacts')
    matches=[a for a in artifacts if a.get('name')=='shared-release-candidate-'+authority['head_sha']]
    if len(matches)!=1:raise DeliveryError('shared_artifact_missing_or_duplicate')
    artifact=matches[0]
    if artifact.get('expired') is not False or type(artifact.get('id')) is not int or not re.fullmatch(r'sha256:[0-9a-f]{64}',str(artifact.get('digest',''))) or type(artifact.get('size_in_bytes')) is not int or not 1<=artifact['size_in_bytes']<=2*1024**3:raise DeliveryError('shared_artifact_metadata')
    metadata=client.get('/repos/'+REPOSITORY+'/actions/artifacts/'+str(artifact['id']))
    if any(metadata.get(k)!=artifact.get(k) for k in ('id','name','digest','size_in_bytes','expired')) or metadata.get('workflow_run',{}).get('id')!=producer['id'] or metadata.get('workflow_run',{}).get('head_sha')!=authority['head_sha']:raise DeliveryError('artifact_producer_binding')
    attempt=root/uuid.uuid4().hex;attempt.mkdir(mode=0o700)
    if shutil.disk_usage(root).free<artifact['size_in_bytes']+512*1024**2:raise DeliveryError('artifact_disk_reserve')
    archive=attempt/'candidate.zip';client.download(artifact['id'],archive,artifact['size_in_bytes'],artifact['digest'][7:])
    verify_download(archive,artifact['size_in_bytes'],artifact['digest'][7:]);safe_extract(archive,attempt/'release')
    release=attempt/'release';record=consumer._json(release/'shared/release.json')
    package=release/'package';manifest=consumer.verify_package(package,expected_manifest_sha256=record.get('manifest_sha256'))
    if record.get('format')!='isurvix-shared-release-v1' or record.get('source_commit')!=authority['head_sha'] or manifest['release_id']!=authority['head_sha'] or record.get('images')!=manifest['images'] or record.get('candidate_only') is not True or record.get('owner_release_approved') is not False or record.get('required_checks')!=checks or 'cloud' not in record.get('editions',[]):raise DeliveryError('shared_record_binding')
    release_gate._checks(record['required_checks'],authority['head_sha'])
    bound=release_gate.release_record(manifest,record['manifest_sha256'],checks,record.get('verification',{}))
    for key in ('source_commit','manifest_sha256','images','editions','supported_from','verification','approval_holds'):
        if record.get(key)!=bound.get(key):raise DeliveryError('shared_install_upgrade_proof_binding')
    if require_checks(client,authority['head_sha'])!=checks or authorize(client,authority['pr'])!=authority:raise DeliveryError('authority_changed_during_acquisition')
    return {**authority,'package':str(package),'manifest_sha256':record['manifest_sha256'],'images':manifest['images'],'supported_from':record.get('supported_from',[]),'artifact_id':artifact['id'],'artifact_sha256':artifact['digest'][7:]}


def render_env(values):
    if not isinstance(values,dict):raise DeliveryError('environment_shape')
    for key,value in values.items():
        if not re.fullmatch('[A-Z][A-Z0-9_]*',key) or not isinstance(value,str) or not value or any(c in value for c in '\r\n\0$`\"\' ;'):raise DeliveryError('environment_literal_values_only')
    return ''.join(key+'='+value+'\n' for key,value in sorted(values.items()))


def read_env(path):
    path=consumer._no_links(path)
    if path.stat().st_size>32768:raise DeliveryError('environment_size')
    values={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):continue
        if '=' not in line:raise DeliveryError('environment_syntax')
        key,value=line.split('=',1)
        if key in values:raise DeliveryError('environment_duplicate')
        values[key]=value
    render_env(values)
    required={'STAGING_HOST','ISURVIX_RELEASE_ID','ISURVIX_APP_IMAGE','ISURVIX_NGINX_IMAGE','ISURVIX_DATA_DIRECTORY','ISURVIX_SECRET_FILE','ISURVIX_TLS_DIRECTORY','ISURVIX_NGINX_CONFIG'}
    if set(values)!=required or values['STAGING_HOST']!=HOST:raise DeliveryError('environment_policy')
    _sha(values['ISURVIX_RELEASE_ID']);consumer._image(values['ISURVIX_APP_IMAGE']);consumer._image(values['ISURVIX_NGINX_IMAGE'])
    return values


def atomic(path,value):
    path=consumer._no_links(path);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.new')
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,separators=(',',':')).encode()+b'\n'
    with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    temporary.chmod(0o600);os.replace(temporary,path)
    if os.name=='posix':
        descriptor=os.open(path.parent,os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


@contextmanager
def lock(root):
    root=consumer._no_links(root)
    if not root.is_dir():raise DeliveryError('private_journal_missing')
    with consumer._no_links(root/'.delivery.lock').open('a+b') as stream:
        try:
            stream.seek(0)
            if not stream.read(1):stream.write(b'0');stream.flush()
            if os.name=='posix':
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            else:
                import msvcrt
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise DeliveryError('another_delivery_is_active') from None
        try:yield
        finally:
            if os.name=='posix':fcntl.flock(stream,fcntl.LOCK_UN)
            else:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def receive(policy,stream,dispatch,*,body_timeout=10):
    # Acquire before accepting any body bytes: a valid SSH key cannot create
    # unbounded simultaneous root processes waiting on incomplete input.
    with lock(policy['root']):return dispatch(read_request(stream,body_timeout=body_timeout))


class Engine:
    def __init__(self,root,environment,host,*,hook=None,authority_check=None):
        self.root=consumer._no_links(root);self.environment=consumer._no_links(environment);self.host=host;self.hook=hook;self.authority_check=authority_check
    def phase(self,state,name):
        state['phase']=name;state['updated_utc']=datetime.now(timezone.utc).isoformat()
        atomic(Path(state['transaction'])/'journal.json',state);atomic(self.root/'active.json',state)
        if self.hook:self.hook(name,state)
    def write_env(self,values):atomic(self.environment,render_env(values).encode())
    def result(self,state,status):
        current=read_env(self.environment);schema=None
        try:
            with closing(sqlite3.connect((Path(current['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3').absolute().as_uri()+'?mode=ro',uri=True)) as database:
                if database.execute("select 1 from sqlite_master where type='table' and name='django_migrations'").fetchone():
                    row=database.execute("select name from django_migrations where app='core' order by name desc limit 1").fetchone()
                    schema=row[0] if row else None
        except sqlite3.DatabaseError:
            if status!='operator_recovery_required':raise
        return {'format':'isurvix-hostinger-receipt-v1','status':status,'pr':state['pr'],'source_release':state['previous_env']['ISURVIX_RELEASE_ID'],'release':current['ISURVIX_RELEASE_ID'],'head_sha':state['head_sha'],'merge_sha':state['merge_sha'],'manifest_sha256':state['manifest_sha256'],'artifact_id':state.get('artifact_id'),'artifact_sha256':state.get('artifact_sha256'),'images':{'app':current['ISURVIX_APP_IMAGE'],'nginx':current['ISURVIX_NGINX_IMAGE']},'core_schema':schema}
    def freeze(self,state):
        self.host.stop();self.phase(state,'operator_recovery_required')
        return self.result(state,'operator_recovery_required')
    def rollback(self,state):
        self.phase(state,'rollback_started');self.host.stop()
        previous=dict(state['previous_env'])
        if state.get('backup_complete'):
            backup.validate_backup(state['backup'])
            if consumer._digest(Path(state['backup'])/'manifest.json')['sha256']!=state['backup_manifest_sha256'] or consumer._digest(Path(state['transaction'])/'retained-records.json')['sha256']!=state['retained_snapshot_sha256']:raise DeliveryError('recovery_proof_changed')
            restored=self.root/('recovered-'+uuid.uuid4().hex)
            backup.restore_backup(state['backup'],restored);self.host.prepare_data(restored)
            retention.assert_retained(
                consumer._json(Path(state['transaction'])/'retained-records.json'), restored/'database.sqlite3',
                source_database=Path(state['backup'])/'database.sqlite3')
            previous['ISURVIX_DATA_DIRECTORY']=str(restored)
        self.write_env(previous);self.host.static_and_check(previous);self.host.start_private(previous);self.host.private_health(previous);self.host.open_public(previous);self.host.public_health(previous)
        state['recovered_env']=previous;self.phase(state,'rolled_back')
        return self.result(state,'rolled_back')
    def run(self,candidate,*,lock_held=False):
        with nullcontext() if lock_held else lock(self.root):
            current=read_env(self.environment);active=self.root/'active.json'
            if active.exists():
                saved=consumer._json(active)
                if saved['phase']=='operator_recovery_required':raise DeliveryError('operator_recovery_required')
                if saved['phase']=='completed' and saved['pr']==candidate['pr'] and saved['head_sha']==candidate['head_sha']:
                    if current!=saved['target_env'] or saved['merge_sha']!=candidate['merge_sha'] or saved['manifest_sha256']!=candidate['manifest_sha256'] or saved.get('artifact_id')!=candidate.get('artifact_id') or saved.get('artifact_sha256')!=candidate.get('artifact_sha256') or candidate['images']!={'app':current['ISURVIX_APP_IMAGE'],'nginx':current['ISURVIX_NGINX_IMAGE']}:raise DeliveryError('completed_replay_binding')
                    self.host.running_health(current)
                    return self.result(saved,'already_running')
                if saved['phase'] not in ('completed','rolled_back'):
                    if saved['phase']=='public_opening':return self.freeze(saved)
                    try:self.rollback(saved)
                    except (ValueError,OSError,sqlite3.DatabaseError):return self.freeze(saved)
                    return self.result(saved,'recovered')
            if current['ISURVIX_RELEASE_ID'] not in candidate.get('supported_from',[]):raise DeliveryError('source_upgrade_not_proven')
            _sha(candidate['head_sha']);_sha(candidate['merge_sha']);_sha(candidate['manifest_sha256'],64)
            for image in candidate['images'].values():consumer._image(image)
            if current['ISURVIX_RELEASE_ID']==candidate['head_sha']:raise DeliveryError('unrecorded_same_release_requires_operator')
            self.host.preflight(current);self.host.running_health(current)
            transaction=self.root/('transaction-'+uuid.uuid4().hex);transaction.mkdir(mode=0o700)
            target=dict(current);target.update(ISURVIX_APP_IMAGE=candidate['images']['app'],ISURVIX_NGINX_IMAGE=candidate['images']['nginx'],ISURVIX_RELEASE_ID=candidate['head_sha'],ISURVIX_DATA_DIRECTORY=str(self.root/('data-'+uuid.uuid4().hex)))
            state={'format':'isurvix-hostinger-delivery-v1','pr':candidate['pr'],'head_sha':candidate['head_sha'],'merge_sha':candidate['merge_sha'],'manifest_sha256':candidate['manifest_sha256'],'approval':candidate['approval'],'artifact_id':candidate.get('artifact_id'),'artifact_sha256':candidate.get('artifact_sha256'),'transaction':str(transaction),'previous_env':current,'target_env':target,'backup':str(transaction/'backup'),'backup_complete':False}
            self.phase(state,'prepared')
            try:
                self.host.load(candidate);self.phase(state,'stopping');self.host.stop()
                self.phase(state,'backup_started')
                source=Path(current['ISURVIX_DATA_DIRECTORY'])
                backup.create_backup(source/'database.sqlite3',source/'media',state['backup'],release_id=current['ISURVIX_RELEASE_ID'],quiesced=True)
                verified=backup.validate_backup(state['backup'])
                atomic(transaction/'retained-records.json',retention.snapshot(Path(state['backup'])/'database.sqlite3'))
                state['backup_manifest_sha256']=consumer._digest(Path(state['backup'])/'manifest.json')['sha256'];state['retained_snapshot_sha256']=consumer._digest(transaction/'retained-records.json')['sha256']
                state['backup_complete']=True;state['media_inventory']={key:value for key,value in verified['files'].items() if key.startswith('media/')};self.phase(state,'backed_up')
                self.phase(state,'restoring');backup.restore_backup(state['backup'],target['ISURVIX_DATA_DIRECTORY']);self.host.prepare_data(target['ISURVIX_DATA_DIRECTORY'])
                self.write_env(target);self.host.preflight(target);self.phase(state,'migrating');self.host.migrate(target);self.host.static_and_check(target)
                retention.assert_retained(
                    consumer._json(transaction/'retained-records.json'),
                    Path(target['ISURVIX_DATA_DIRECTORY'])/'database.sqlite3',
                    source_database=Path(state['backup'])/'database.sqlite3')
                media=consumer._files(Path(target['ISURVIX_DATA_DIRECTORY'])/'media')
                if {'media/'+key:consumer._digest(path) for key,path in media.items()}!=state['media_inventory']:raise DeliveryError('evidence_changed_during_migration')
                self.host.start_private(target);self.host.private_health(target);self.phase(state,'private_ready')
                if self.authority_check:self.authority_check()
                # Persist BEFORE the listener could accept any human/API write.
                self.phase(state,'public_opening');self.host.open_public(target);self.host.public_health(target)
                self.phase(state,'completed');return self.result(state,'completed')
            except (ValueError,OSError,subprocess.SubprocessError,sqlite3.DatabaseError) as error:
                # Keep bounded diagnostics in the private journal without storing
                # exception text, which can contain paths or provider responses.
                failed_phase=state['phase']
                state['failure_phase']=failed_phase
                state['failure_type']=type(error).__name__
                self.phase(state,'failure_recorded')
                if failed_phase in ('public_opening','completed'):return self.freeze(state)
                try:return self.rollback(state)
                except (ValueError,OSError,subprocess.SubprocessError,sqlite3.DatabaseError):return self.freeze(state)


def _health_body(raw,release):
    value=_json(raw)
    if not isinstance(value,dict) or value.get('status')!='ready' or value.get('release')!=release:raise DeliveryError('readiness_release_mismatch')


def validate_compose(config,environment=None):
    if not isinstance(config,dict) or set(config.get('services',{}))!={'web','proxy'}:raise DeliveryError('runtime_services_policy')
    allowed={'web':{'/data','/run/isurvix-config/ifield_settings.py'},'proxy':{'/etc/nginx/nginx.conf','/data/static','/tls'}}
    mail_target='/run/private/ifield-notification.json'
    mail_source='/etc/isurvix-staging/ifield-notification.json'
    web_environment=config['services']['web'].get('environment',{})
    if not isinstance(web_environment,dict):raise DeliveryError('runtime_environment_policy')
    mail_enabled=web_environment.get('ISURVIX_NOTIFICATION_EMAIL_ENABLED')=='True'
    if mail_enabled:
        if web_environment.get('ISURVIX_NOTIFICATION_CREDENTIALS_FILE')!=mail_target:raise DeliveryError('runtime_mail_credential_policy')
        allowed['web'].add(mail_target)
    for name,user in [('web','10001:10001'),('proxy','101:101')]:
        value=config['services'][name];consumer._image(value.get('image'))
        if value.get('user')!=user or value.get('read_only') is not True or set(value.get('cap_drop',[]))!={'ALL'} or not any(option in value.get('security_opt',[]) for option in ('no-new-privileges:true','no-new-privileges')) or value.get('privileged') or value.get('cap_add') or value.get('devices') or value.get('network_mode')=='host' or value.get('pid')=='host':raise DeliveryError('runtime_privilege_policy')
        if name=='web' and value.get('ports'):raise DeliveryError('public_web_forbidden')
        targets=set()
        for volume in value.get('volumes',[]):
            if volume.get('type')!='bind' or volume.get('target') not in allowed[name] or volume['target'] in targets or (volume['target']!='/data' and volume.get('read_only') is not True):raise DeliveryError('runtime_mount_policy')
            targets.add(volume['target'])
            if volume['target']==mail_target and volume.get('source')!=mail_source:raise DeliveryError('runtime_mail_credential_policy')
            if environment:
                expected={'/data':environment['ISURVIX_DATA_DIRECTORY'],'/data/static':str(Path(environment['ISURVIX_DATA_DIRECTORY'])/'static'),'/tls':environment['ISURVIX_TLS_DIRECTORY'],'/etc/nginx/nginx.conf':environment['ISURVIX_NGINX_CONFIG']}.get(volume['target'])
                if expected is not None and volume.get('source')!=expected:raise DeliveryError('runtime_mount_source_changed')
        if '/data' not in targets and name=='web' or name=='proxy' and targets!=allowed['proxy']:raise DeliveryError('runtime_required_mount_missing')
        if name=='web' and mail_enabled and mail_target not in targets:raise DeliveryError('runtime_mail_credential_policy')
    ports=config['services']['proxy'].get('ports',[])
    actual={(p.get('host_ip'),str(p.get('published')),p.get('target'),p.get('protocol','tcp')) for p in ports}
    expected={('127.0.0.1','8080',8080,'tcp'),('127.0.0.1','8443',8443,'tcp'),('0.0.0.0','443',8443,'tcp')}
    if len(ports)!=3 or actual!=expected:raise DeliveryError('runtime_public_ports_policy')


class Host:
    def __init__(self,policy,runner=subprocess.run):self.policy=policy;self.runner=runner
    def docker(self,*args):
        try:
            result=self.runner(['docker','--host','unix:///var/run/docker.sock',*map(str,args)],capture_output=True,check=False,timeout=600)
        except (OSError,subprocess.SubprocessError):raise DeliveryError('local_docker_operation_failed') from None
        if result.returncode or len(result.stdout)>16*1024*1024:raise DeliveryError('local_docker_operation_failed')
        return result.stdout
    def dc(self,*args,private=False):
        base=['compose','--env-file',self.policy['environment_file'],'-p',self.policy['project']]
        for path in self.policy['compose_files'][:1 if private else 2]:base+=['-f',path]
        return self.docker(*base,*args)
    def preflight(self,env):
        config=_json(self.dc('config','--format','json'));validate_compose(config,env)
        if config['services']['web']['image']!=env['ISURVIX_APP_IMAGE'] or config['services']['proxy']['image']!=env['ISURVIX_NGINX_IMAGE']:raise DeliveryError('rendered_image_identity_changed')
        data=Path(env['ISURVIX_DATA_DIRECTORY']);size=(data/'database.sqlite3').stat().st_size+sum(path.stat().st_size for path in consumer._files(data/'media').values())
        if shutil.disk_usage(self.policy['root']).free<3*size+512*1024**2:raise DeliveryError('insufficient_backup_restore_reserve')
    def stop(self):
        self.dc('stop','--timeout','60','proxy','web')
        raw=self.dc('ps','--all','--format','json').decode().strip()
        rows=_json(raw) if raw.startswith('[') else [_json(line) for line in raw.splitlines() if line]
        if any(row.get('Service') in ('web','proxy') and row.get('State') not in ('exited','dead','created') for row in rows):raise DeliveryError('writers_not_stopped')
    def load(self,candidate):consumer.load_images(candidate['package'],acknowledge_draft=True)
    def prepare_data(self,path):
        root=consumer._no_links(path)
        for name in ('static','upload-tmp'):(root/name).mkdir(mode=0o755 if name=='static' else 0o700,exist_ok=True)
        for directory,dirs,files in os.walk(root,followlinks=False):
            for name in dirs+files:consumer._no_links(Path(directory)/name)
            if os.name=='posix':os.chown(directory,10001,10001)
            Path(directory).chmod(0o755 if Path(directory)==root/'static' else 0o700)
            for name in files:
                file=Path(directory)/name
                if os.name=='posix':os.chown(file,10001,10001)
                file.chmod(0o600)
    def migrate(self,env):self.dc('run','--rm','--no-deps','--pull','never','web','python','manage.py','migrate','--noinput')
    def static_and_check(self,env):
        self.dc('run','--rm','--no-deps','--pull','never','web','python','manage.py','collectstatic','--noinput')
        self.dc('run','--rm','--no-deps','--pull','never','web','python','manage.py','check','--deploy','--fail-level','WARNING')
    def start_private(self,env):
        self.dc('up','-d','--no-deps','--pull','never','--no-build','--wait','--wait-timeout','180','web')
        # Start ONLY proxy using the trusted original loopback-only base. The
        # already-running web retains the reviewed public/login override.
        self.dc('up','-d','--no-deps','--force-recreate','--pull','never','--no-build','--wait','--wait-timeout','180','proxy',private=True)
    def identity(self,env):
        for service,image_key in [('web','ISURVIX_APP_IMAGE'),('proxy','ISURVIX_NGINX_IMAGE')]:
            identity=self.dc('ps','-q',service).decode().strip()
            if not re.fullmatch('[0-9a-f]{12,64}',identity):raise DeliveryError('runtime_container_missing')
            actual=self.docker('inspect','--format','{{.Image}}',identity).decode().strip()
            if actual!=env[image_key]:raise DeliveryError('runtime_image_mismatch')
        if self.dc('exec','-T','web','cat','/app/RELEASE').decode().strip()!=env['ISURVIX_RELEASE_ID']:raise DeliveryError('runtime_baked_release_mismatch')
    def private_health(self,env):
        self.identity(env)
        proxy=self.dc('ps','-q','proxy').decode().strip()
        ports=_json(self.docker('inspect','--format','{{json .NetworkSettings.Ports}}',proxy))
        bindings=[binding for rows in ports.values() if rows for binding in rows]
        if not bindings or any(b.get('HostIp')!='127.0.0.1' or b.get('HostPort') not in ('8080','8443') for b in bindings):raise DeliveryError('candidate_listener_not_private')
        self.dc('exec','-T','web','python','/app/deploy/healthcheck.py')
        try:
            with socket.create_connection(('127.0.0.1',8443),timeout=10) as raw:
                with ssl.create_default_context().wrap_socket(raw,server_hostname=HOST) as secure:
                    secure.sendall(('GET /ops/health/ready/ HTTP/1.1\r\nHost: '+HOST+':8443\r\nConnection: close\r\n\r\n').encode())
                    response=HTTPResponse(secure);response.begin();body=response.read(16385)
                    if response.status!=200 or len(body)>16384:raise DeliveryError('private_tls_readiness')
                    _health_body(body,env['ISURVIX_RELEASE_ID'])
        except (OSError,ValueError):raise DeliveryError('private_tls_readiness') from None
    def open_public(self,env):self.dc('up','-d','--no-deps','--force-recreate','--pull','never','--no-build','--wait','--wait-timeout','180','proxy')
    def public_health(self,env):
        self.identity(env)
        try:
            with build_opener(_NoRedirect()).open('https://'+HOST+'/ops/health/ready/',timeout=15) as response:
                body=response.read(16385)
                if response.status!=200 or len(body)>16384:raise DeliveryError('public_tls_readiness')
                _health_body(body,env['ISURVIX_RELEASE_ID'])
        except (HTTPError,URLError,OSError):raise DeliveryError('public_tls_readiness') from None
    def running_health(self,env):self.public_health(env)


def trusted_file(path):
    path=consumer._no_links(path);info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:raise DeliveryError('trusted_operator_file_required')
    return path


def load_policy(path):
    policy=consumer._json(trusted_file(path))
    required={'format','enabled','repository','branch','owner','host','project','root','environment_file','compose_files','initial_data'}
    if set(policy)!=required or policy['format']!='isurvix-hostinger-policy-v1' or policy['enabled'] is not True or (policy['repository'],policy['branch'],policy['owner'],policy['host'])!=(REPOSITORY,BRANCH,OWNER,HOST) or not re.fullmatch('[a-z0-9-]{1,63}',policy['project']):raise DeliveryError('operator_policy_not_enabled')
    if not isinstance(policy['compose_files'],list) or len(policy['compose_files'])!=2:raise DeliveryError('trusted_two_file_runtime_required')
    for file in [policy['environment_file'],*policy['compose_files']]:trusted_file(file)
    root=consumer._no_links(policy['root']);info=root.stat()
    if not root.is_absolute() or not root.is_dir() or info.st_uid!=0 or info.st_mode&0o077:raise DeliveryError('private_root_journal_required')
    initial=consumer._no_links(policy['initial_data'])
    if root.is_relative_to(initial) or initial.is_relative_to(root):raise DeliveryError('journal_must_be_separate_from_initial_data')
    current=read_env(policy['environment_file']);data=consumer._no_links(current['ISURVIX_DATA_DIRECTORY'])
    if data!=consumer._no_links(policy['initial_data']) and (data.parent!=root or not re.fullmatch('(data|recovered)-[0-9a-f]{32}',data.name)):raise DeliveryError('persistent_data_path_not_authorized')
    return policy


def main():
    try:
        if os.name!='posix' or os.geteuid()!=0 or not sys.flags.isolated:raise DeliveryError('isolated_root_controller_required')
        if os.environ.get('SSH_ORIGINAL_COMMAND','') not in ('','deliver'):raise DeliveryError('forced_command_only')
        policy=load_policy('/etc/isurvix-delivery/policy.json')
        def dispatch(request):
            client=GitHub(request.pop('github_token'))
            authority=authorize(client,request['pr']);candidate=acquire(client,authority,Path(policy['root'])/'artifacts')
            # Recheck source/approval/checks immediately before maintenance.
            if authorize(client,request['pr'])!=authority:raise DeliveryError('authority_changed_before_maintenance')
            require_checks(client,authority['head_sha'])
            def still_authorized():
                if authorize(client,request['pr'])!=authority:raise DeliveryError('authority_changed_before_publication')
                require_checks(client,authority['head_sha'])
            host=Host(policy);return Engine(policy['root'],policy['environment_file'],host,authority_check=still_authorized).run(candidate,lock_held=True)
        result=receive(policy,sys.stdin.buffer,dispatch)
        print(json.dumps(result,sort_keys=True))
        return 0 if result['status'] in ('completed','already_running') else 2
    except Exception:
        # Neither arbitrary exception messages, request/token, signed storage URL
        # nor candidate process stdout is ever returned to the SSH caller.
        print(json.dumps({'status':'blocked','code':'delivery_not_completed','operator_diagnostics':'Inspect private journal and exact GitHub checks.'}))
        return 2


if __name__=='__main__':raise SystemExit(main())
