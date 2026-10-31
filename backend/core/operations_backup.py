"""Private, quiesced SQLite/media snapshots and verified new-target recovery.

Hashes detect corruption, not an administrator replacing both bytes and manifest.
The operator must stop every writer before confirming quiescence. No live restore.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import unicodedata


def _no_links(path):
    path=Path(path).absolute()
    for part in (path,*path.parents):
        if part.is_symlink() or getattr(part,'is_junction',lambda:False)():
            raise ValueError('Backup/recovery paths must not contain symbolic links or junctions.')
    return path


def _name(value):
    if not isinstance(value,str) or not value or '\\' in value:
        raise ValueError('Invalid relative backup filename.')
    name=PurePosixPath(value)
    if name.is_absolute() or str(name)!=value:
        raise ValueError('Invalid relative backup filename.')
    for part in name.parts:
        if (part in {'.','..'} or part.endswith(('.', ' ')) or
                any(ord(c)<32 or c in ':<>"|?*' for c in part) or
                part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]} or
                re.fullmatch(r'[^.]{1,6}~\d+(?:\..*)?',part,re.I)):
            raise ValueError('Backup filename is not portable to the recovery filesystem.')
    return unicodedata.normalize('NFC',value).casefold()


def _names(names):
    keys=set()
    for name in names:
        key=_name(name)
        if key in keys:
            raise ValueError('Backup contains conflicting filenames.')
        keys.add(key)
    for key in keys:
        parts=key.split('/')
        if any('/'.join(parts[:i]) in keys for i in range(1,len(parts))):
            raise ValueError('Backup contains file/directory conflicts.')


def _files(root):
    root=_no_links(root)
    if not root.is_dir():raise ValueError('The media/backup directory is unavailable.')
    result={}
    for folder,dirs,files in os.walk(root,followlinks=False):
        for name in dirs:
            _no_links(Path(folder)/name)
        for name in files:
            path=_no_links(Path(folder)/name)
            if not path.is_file():raise ValueError('Backup accepts regular files only.')
            result[path.relative_to(root).as_posix()]=path
    return result


def _signature(path):
    stat=path.stat()
    return stat.st_size,stat.st_mtime_ns,stat.st_ino


def _digest(path):
    _no_links(path)
    digest=hashlib.sha256();size=0
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024):digest.update(chunk);size+=len(chunk)
    return {'size':size,'sha256':digest.hexdigest()}


def _copy(source,target):
    _no_links(source);before=_signature(source)
    target.parent.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256();size=0
    with source.open('rb') as src,target.open('xb') as dst:
        while chunk:=src.read(1024*1024):
            dst.write(chunk);digest.update(chunk);size+=len(chunk)
        dst.flush();os.fsync(dst.fileno())
    if before!=_signature(source):raise ValueError('Source changed during backup/recovery. Stop writers and retry into a new target.')
    return {'size':size,'sha256':digest.hexdigest()}


def _reserve(destination):
    destination=_no_links(destination)
    if destination.exists():raise ValueError('Destination already exists; select a new disposable directory.')
    if not destination.parent.is_dir():raise ValueError('Destination parent must be an existing private directory.')
    try:destination.mkdir(mode=0o700)
    except FileExistsError:raise ValueError('Destination already exists.') from None
    return destination


def _database_ok(path):
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute('pragma quick_check').fetchone()!=('ok',):raise ValueError('Backup database integrity check failed.')
    except sqlite3.DatabaseError:
        raise ValueError('Backup database integrity check failed.') from None


def _publish(target,manifest):
    with (target/'manifest.json').open('x',encoding='utf-8') as f:
        json.dump(manifest,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def _incomplete(target):
    # Preserve failed output for diagnosis; never mark it as a completed backup.
    try:(target/'INCOMPLETE').write_text('Incomplete operation. Do not restore or serve this directory.\n')
    except OSError:pass


def create_backup(database_path,media_root,destination,*,release_id,quiesced=False):
    if quiesced is not True:raise ValueError('Stop web/worker writers and explicitly confirm quiescence.')
    if not isinstance(release_id,str) or not re.fullmatch('[0-9a-f]{40}',release_id):
        raise ValueError('Specify the exact reviewed 40-character release commit.')
    database=_no_links(database_path);media=_no_links(media_root);destination=_no_links(destination)
    if not database.is_file():raise ValueError('A regular SQLite database file is required.')
    if destination.is_relative_to(media):raise ValueError('Backup destination must be outside the media directory.')
    sources=_files(media);names=['database.sqlite3',*('media/'+n for n in sources)]
    _names(names)
    signatures={n:_signature(path) for n,path in sources.items()}
    target=_reserve(destination)
    try:
        (target/'media').mkdir(mode=0o700)
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target/'database.sqlite3')) as dst:
            src.backup(dst)
        _database_ok(target/'database.sqlite3')
        files={'database.sqlite3':_digest(target/'database.sqlite3')}
        for name,path in sorted(sources.items()):files['media/'+name]=_copy(path,target/'media'/name)
        after=_files(media)
        if set(after)!=set(sources) or any(_signature(after[n])!=sig for n,sig in signatures.items()):
            raise ValueError('Media changed while backing up. Stop all writers and retry into a new target.')
        manifest={'schema':1,'release_id':release_id,'created_utc':datetime.now(timezone.utc).isoformat(),
                  'quiescence_confirmed':True,'files':files}
        _publish(target,manifest)
        return {'status':'complete','release_id':release_id,'files':len(files),'media_files':len(sources)}
    except Exception:
        _incomplete(target)
        raise


def _unique_json(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate backup manifest key.')
        result[key]=value
    return result


def validate_backup(backup_dir):
    root=_no_links(backup_dir)
    if not root.is_dir():raise ValueError('Backup directory is unavailable.')
    manifest_file=_no_links(root/'manifest.json')
    if not manifest_file.is_file() or manifest_file.stat().st_size>16*1024*1024:
        raise ValueError('A complete, bounded backup manifest is required.')
    try:
        manifest=json.loads(manifest_file.read_text(encoding='utf-8'),object_pairs_hook=_unique_json)
    except (UnicodeError,json.JSONDecodeError):raise ValueError('Backup manifest is invalid.') from None
    if (not isinstance(manifest,dict) or set(manifest)!={'schema','release_id','created_utc','quiescence_confirmed','files'} or
            manifest['schema']!=1 or manifest['quiescence_confirmed'] is not True or
            not isinstance(manifest['release_id'],str) or not re.fullmatch('[0-9a-f]{40}',manifest['release_id'])):
        raise ValueError('Backup format/release is invalid.')
    files=manifest['files']
    if not isinstance(files,dict) or not files or len(files)>100000 or 'database.sqlite3' not in files:
        raise ValueError('Backup file inventory is invalid.')
    _names(files)
    for name,receipt in files.items():
        if name!='database.sqlite3' and not name.startswith('media/'):
            raise ValueError('Unsupported backup path.')
        if (not isinstance(receipt,dict) or set(receipt)!={'size','sha256'} or type(receipt['size']) is not int or receipt['size']<0 or
                not isinstance(receipt['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',receipt['sha256'])):
            raise ValueError('Backup file receipt is invalid.')
    actual=_files(root)
    if set(actual)!={'manifest.json',*files}:
        raise ValueError('Backup has missing or unexpected files.')
    for name,receipt in files.items():
        if _digest(actual[name])!=receipt:raise ValueError('Backup file digest/size mismatch.')
    _database_ok(root/'database.sqlite3')
    return manifest


def restore_backup(backup_dir,destination):
    root=_no_links(backup_dir);destination=_no_links(destination)
    if destination.is_relative_to(root):raise ValueError('Restore target must be outside the backup directory.')
    if destination.exists():raise ValueError('Restore destination must be a new disposable directory.')
    manifest=validate_backup(root)  # Every path/hash/database checked before target creation.
    target=_reserve(destination)
    try:
        (target/'media').mkdir(mode=0o700)
        for name,receipt in sorted(manifest['files'].items()):
            if _copy(root/name,target/name)!=receipt:raise ValueError('Backup changed during restoration.')
        _database_ok(target/'database.sqlite3');_publish(target,manifest)
        return {'status':'complete','release_id':manifest['release_id'],'files':len(manifest['files'])}
    except Exception:
        _incomplete(target)
        raise
