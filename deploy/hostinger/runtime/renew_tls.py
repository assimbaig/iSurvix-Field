"""Root-operated, versioned TLS publication; never prints key/certificate bytes.

The mounted TLS directory stays fixed. Both exposed filenames resolve through
one atomically replaced `current` symlink, so readers cannot see a new cert with
an old key after an interrupted copy. Prior generations are deliberately kept.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid


class TLSFailure(ValueError):pass


def _config(value):
    keys={'host','lineage','tls_directory','environment_file','compose_files','project'}
    if not isinstance(value,dict) or set(value)!=keys or value['host']!='app.isurvix.com':
        raise TLSFailure('Use the reviewed exact-host renewal configuration.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',str(value['project'])):
        raise TLSFailure('Invalid isolated Compose project.')
    paths=[value[k] for k in ('lineage','tls_directory','environment_file')]
    if not isinstance(value['compose_files'],list) or len(value['compose_files'])!=2:
        raise TLSFailure('Include the shared Compose file and public-origin override.')
    paths+=value['compose_files']
    if any(not isinstance(p,str) or not Path(p).is_absolute() or any(c in p for c in '\r\n\0') for p in paths):
        raise TLSFailure('Use absolute controlled operator paths.')
    return value


def _bounded(path,limit):
    try:
        if not stat.S_ISREG(path.stat().st_mode):raise TLSFailure('Certificate inputs must be regular files.')
        with path.open('rb') as stream:data=stream.read(limit+1)
    except OSError:raise TLSFailure('Certificate inputs are unavailable.') from None
    if not data or len(data)>limit:raise TLSFailure('Certificate input size is invalid.')
    return data


def _run(runner,command):
    try:
        result=runner(command,input=b'',capture_output=True,timeout=30,check=False)
    except (OSError,subprocess.SubprocessError):raise TLSFailure('The controlled certificate/proxy command could not run.') from None
    if result.returncode:raise TLSFailure('Certificate validation or proxy reload failed; private output suppressed.')
    return result.stdout


def validate_certificate(config,*,openssl='openssl',runner=subprocess.run):
    lineage=Path(config['lineage']);cert=lineage/'fullchain.pem';key=lineage/'privkey.pem'
    cert_bytes=_bounded(cert,1024*1024);key_bytes=_bounded(key,128*1024)
    # `x509 -checkhost` may exit zero on a hostname mismatch (Ubuntu's
    # OpenSSL). `verify -verify_hostname` has failure exit semantics. Trust
    # the operator's Certbot lineage explicitly; public trust is separately
    # checked at the actual HTTPS endpoint, never inferred from this helper.
    _run(runner,[openssl,'verify','-partial_chain','-trusted',str(cert),'-verify_hostname',config['host'],'-purpose','sslserver',str(cert)])
    _run(runner,[openssl,'x509','-in',str(cert),'-noout','-checkend','86400'])
    cert_public=_run(runner,[openssl,'x509','-in',str(cert),'-pubkey','-noout'])
    key_public=_run(runner,[openssl,'pkey','-in',str(key),'-pubout'])
    if not cert_public or cert_public.strip()!=key_public.strip():raise TLSFailure('The certificate and private key do not match.')
    return cert_bytes,key_bytes


def _target(path):
    path=Path(path).absolute()
    for part in (path,*path.parents):
        if part.is_symlink() or getattr(part,'is_junction',lambda:False)():
            raise TLSFailure('The managed TLS directory must not use symbolic/junction parents.')
    return path


def _permissions(path,mode,uid=0,gid=101):
    if os.name=='posix':os.chown(path,uid,gid)
    os.chmod(path,mode)


@contextmanager
def _lock(path):
    with path.open('a+b') as stream:
        _permissions(path,0o600,0,0)
        try:
            if os.name=='posix':
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            else:
                import msvcrt
                stream.seek(0)
                if not stream.read(1):stream.write(b'0');stream.flush()
                stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise TLSFailure('Another certificate publication is active.') from None
        try:yield
        finally:
            if os.name=='posix':fcntl.flock(stream,fcntl.LOCK_UN)
            else:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def _sync(directory):
    if os.name=='posix':
        descriptor=os.open(directory,os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def _switch(tls,value):
    staging=tls/('.next-'+uuid.uuid4().hex)
    os.symlink(value,staging,target_is_directory=True)
    os.replace(staging,tls/'current');_sync(tls)


def _compose(config):
    command=['docker','--host','unix:///var/run/docker.sock','compose','--env-file',config['environment_file'],'-p',config['project']]
    for path in config['compose_files']:command+=['-f',path]
    return command+['exec','-T','proxy','nginx','-p','/tmp/nginx/','-c','/etc/nginx/nginx.conf']


def publish(config,*,reload=True,openssl='openssl',runner=subprocess.run,renewed_lineage=None):
    config=_config(config)
    if renewed_lineage and Path(renewed_lineage).absolute()!=Path(config['lineage']).absolute():
        raise TLSFailure('This renewal hook handles only the approved certificate lineage.')
    cert,key=validate_certificate(config,openssl=openssl,runner=runner)
    tls=_target(config['tls_directory'])
    if tls.exists() and not tls.is_dir():raise TLSFailure('Use a new or previously managed TLS directory.')
    for name in ('fullchain.pem','privkey.pem'):
        path=tls/name
        if (path.exists() or path.is_symlink()) and (not path.is_symlink() or os.readlink(path)!='current/'+name):
            raise TLSFailure('Existing unmanaged TLS inputs were preserved; select a new managed directory.')
    tls.mkdir(mode=0o750,parents=False,exist_ok=True);_permissions(tls,0o750)
    with _lock(tls/'.renewal.lock'):
        current=tls/'current';previous=None
        if current.exists() or current.is_symlink():
            if not current.is_symlink():raise TLSFailure('The managed current-generation pointer is invalid.')
            previous=os.readlink(current)
            if not re.fullmatch(r'generations/[0-9a-f]{32}',previous) or not (tls/previous).is_dir() or (tls/previous).is_symlink():
                raise TLSFailure('The saved TLS generation is invalid.')
            if _bounded(tls/previous/'fullchain.pem',1024*1024)==cert and _bounded(tls/previous/'privkey.pem',128*1024)==key:
                # Disk equality does not prove a previous invocation reached
                # the reload signal. A retry reuses files/generation while
                # validating and signaling the actual runtime again.
                if reload:
                    _run(runner,_compose(config)+['-t']);_run(runner,_compose(config)+['-s','reload'])
                return {'changed':False,'reloaded':reload,'host':config['host']}
        elif reload:raise TLSFailure('First publication requires explicit --no-reload before the proxy starts.')
        generations=tls/'generations'
        if generations.is_symlink():raise TLSFailure('Managed generations must not be redirected.')
        generations.mkdir(mode=0o710,exist_ok=True);_permissions(generations,0o710)
        token=uuid.uuid4().hex;generation=generations/token;generation.mkdir(mode=0o700);_permissions(generation,0o700,101,101)
        for name,payload,mode in [('fullchain.pem',cert,0o444),('privkey.pem',key,0o400)]:
            file=generation/name
            with file.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
            _permissions(file,mode,101,101)
        _sync(generation);_sync(generations)
        for name in ('fullchain.pem','privkey.pem'):
            if not (tls/name).is_symlink():os.symlink('current/'+name,tls/name)
        _switch(tls,'generations/'+token)
        if reload:
            try:
                _run(runner,_compose(config)+['-t']);_run(runner,_compose(config)+['-s','reload'])
            except TLSFailure:
                _switch(tls,previous)
                try:_run(runner,_compose(config)+['-t']);_run(runner,_compose(config)+['-s','reload'])
                except TLSFailure:raise TLSFailure('Renewal failed; old files restored, but proxy recovery requires operator inspection.') from None
                raise TLSFailure('Renewal failed; the previous complete TLS generation was restored.') from None
        return {'changed':True,'reloaded':reload,'host':config['host'],'certificate_sha256':hashlib.sha256(cert).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path);parser.add_argument('--no-reload',action='store_true');args=parser.parse_args()
    try:
        if os.name!='posix' or os.geteuid()!=0:raise TLSFailure('Run this operator hook as root on the Linux host.')
        path=_target(args.config);metadata=path.stat()
        if metadata.st_uid!=0 or metadata.st_mode&0o022:raise TLSFailure('Renewal configuration must be root-owned and not group/world writable.')
        config=json.loads(path.read_text(encoding='utf-8'))
        result=publish(config,reload=not args.no_reload,renewed_lineage=os.environ.get('RENEWED_LINEAGE'))
        print(json.dumps(result,sort_keys=True))
    except (TLSFailure,OSError,ValueError,KeyError) as error:
        # Error strings from subprocesses, certificate/key bytes and environment
        # values never reach stdout/stderr. Controlled errors are sufficient.
        parser.exit(2,'TLS publication failed; retained files are preserved. Inspect the controlled operator configuration and service status.\n')


if __name__=='__main__':main()
