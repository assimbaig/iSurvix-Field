"""Review/build helpers. No deployment or package/model download occurs here."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent


def image_reference(value):
    if not re.fullmatch(r'(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}',str(value)):
        raise ValueError('Use a reviewed registry image pinned by its verified SHA256 manifest digest.')
    return value


def prepare_release(repository,target,release_id):
    repository=Path(repository).resolve();target=Path(target).absolute()
    if target.exists():raise ValueError('Build export target already exists; choose a new empty path.')
    if not re.fullmatch(r'[0-9a-f]{40}',str(release_id)):raise ValueError('Use an exact reviewed commit.')
    def git(*args):return subprocess.check_output(['git',*args],cwd=repository,text=True).strip()
    if git('rev-parse','HEAD')!=release_id or git('status','--porcelain'):
        raise ValueError('The checkout must be clean and match the exact reviewed release commit.')
    payload=subprocess.check_output(['git','archive','--format=zip',release_id],cwd=repository)
    with ZipFile(io.BytesIO(payload)) as archive:
        # This is an exact local Git export, never an uploaded customer archive.
        for entry in archive.infolist():
            path=Path(entry.filename)
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(entry.external_attr>>16):
                raise ValueError('Unsafe or symbolic source archive member; no export was created.')
        target.mkdir(parents=True,mode=0o700)
        archive.extractall(target)
    (target/'RELEASE').write_text(release_id+'\n',encoding='ascii')
    return {'release_id':release_id,'context':str(target),'source':'clean tracked Git export','private_ignored_files_copied':False}


def validate_environment(values,*,initialize=False):
    required=['STAGING_HOST','ISURVIX_RELEASE_ID','ISURVIX_APP_IMAGE','ISURVIX_NGINX_IMAGE',
              'ISURVIX_DATA_DIRECTORY','ISURVIX_SECRET_FILE','ISURVIX_TLS_DIRECTORY','ISURVIX_NGINX_CONFIG']
    if any(not values.get(name,'').strip() for name in required):raise ValueError('Missing required private staging configuration; use deploy/.env.example.')
    if not re.fullmatch(r'[0-9a-f]{40}',values['ISURVIX_RELEASE_ID']):raise ValueError('Release must be a complete reviewed commit.')
    images={name:image_reference(values[name]) for name in ['ISURVIX_APP_IMAGE','ISURVIX_NGINX_IMAGE']}
    root=Path(values['ISURVIX_DATA_DIRECTORY'])
    if not root.is_absolute() or not all((root/name).is_dir() for name in ['media','static','upload-tmp']):
        raise ValueError('Create the intended persistent data/media/static/upload-tmp directories first.')
    if not initialize and not (root/'database.sqlite3').is_file():raise ValueError('Persistent database missing; only explicit initialization may create a new database.')
    secret=Path(values['ISURVIX_SECRET_FILE'])
    if not secret.is_absolute() or not secret.is_file():raise ValueError('Private secret file is missing.')
    if secret.resolve().is_relative_to((root/'media').resolve()) or secret.resolve().is_relative_to((root/'static').resolve()):
        raise ValueError('Keep private secret files outside evidence/static directories.')
    config=Path(values['ISURVIX_NGINX_CONFIG'])
    if not config.is_absolute() or not config.is_file():raise ValueError('Render and review the absolute Nginx configuration path first.')
    tls=Path(values['ISURVIX_TLS_DIRECTORY'])
    if not tls.is_absolute() or not all((tls/name).is_file() for name in ['fullchain.pem','privkey.pem']):raise ValueError('Supply approved TLS certificate and key files; this tool never requests certificates.')
    expected=render_nginx(host=values['STAGING_HOST'],upstream='web:8000',static_root='/data/static',
        certificate='/tls/fullchain.pem',key='/tls/privkey.pem',http_port=8080,https_port=8443)
    if config.read_text(encoding='utf-8')!=expected:
        raise ValueError('Nginx configuration differs from the reviewed generated private-media/TLS policy. Render and review it again.')
    return {'release_id':values['ISURVIX_RELEASE_ID'],'images':images,'data_root':str(root),'initialize':initialize,'deployment_performed':False}


def _path(value):
    value=str(value).replace('\\','/')
    if not re.fullmatch(r'[A-Za-z0-9 /:_.-]+',value) or not value.startswith(('/',)) and not re.match(r'^[A-Za-z]:/',value):
        raise ValueError('Use an absolute, directive-safe path.')
    return value.rstrip('/')


def render_nginx(*,host,upstream,static_root,certificate,key,http_port=80,https_port=443,listen_address='0.0.0.0'):
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',host) or '.' not in host or '..' in host:
        raise ValueError('Use one explicit DNS hostname.')
    if not re.fullmatch(r'[A-Za-z0-9._-]+:[0-9]{1,5}',upstream) or not 1<=int(upstream.rsplit(':',1)[1])<=65535:
        raise ValueError('Use a literal host:port upstream, without directive syntax.')
    if listen_address not in {'0.0.0.0','127.0.0.1'}:raise ValueError('Choose an explicit loopback or container listener.')
    if not all(type(port) is int and 1<=port<=65535 for port in [http_port,https_port]):raise ValueError('Invalid proxy listener port.')
    values={'HOST':host,'UPSTREAM':upstream,'STATIC_ROOT':_path(static_root),'CERTIFICATE':_path(certificate),'KEY':_path(key),
            'HTTP_PORT':str(http_port),'HTTPS_PORT':str(https_port),'LISTEN_ADDRESS':listen_address}
    result=(HERE/'nginx.conf.template').read_text(encoding='utf-8')
    for name,value in values.items():result=result.replace('@@'+name+'@@',value)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    render=commands.add_parser('render-nginx')
    for name in ['host','upstream','static-root','certificate','key','output']:render.add_argument('--'+name,required=True)
    render.add_argument('--http-port',type=int,default=80);render.add_argument('--https-port',type=int,default=443)
    render.add_argument('--listen-address',default='0.0.0.0')
    image=commands.add_parser('check-image');image.add_argument('reference')
    prepare=commands.add_parser('prepare-release');prepare.add_argument('--repository',type=Path,default=HERE.parent)
    prepare.add_argument('--output',type=Path,required=True);prepare.add_argument('--release-id',required=True)
    validate=commands.add_parser('validate');validate.add_argument('--initialize-database',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='check-image':print(image_reference(args.reference));return
        if args.command=='prepare-release':print(json.dumps(prepare_release(args.repository,args.output,args.release_id)));return
        if args.command=='validate':print(json.dumps(validate_environment(os.environ,initialize=args.initialize_database)));return
        data=vars(args);data.pop('command');output=Path(data.pop('output'))
        if output.exists():raise ValueError('Choose a new rendered configuration path; existing files are preserved.')
        config=render_nginx(**{name.replace('-','_'):value for name,value in data.items()})
        output.write_text(config,encoding='utf-8')
        print(json.dumps({'rendered':str(output),'host':args.host,'direct_media':'denied'}))
    except (ValueError,OSError) as error:parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
