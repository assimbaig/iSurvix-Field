"""Fail-closed hosted deployment; persistent data and outbound compute are separate.

No directories, keys or databases are created by importing these settings.
"""
import ipaddress
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403


def _required(name):
    value=os.environ.get(name,'').strip()
    if not value:raise ImproperlyConfigured('Missing staging configuration: '+name)
    return value


if os.environ.get('DEBUG','False')!='False':
    raise ImproperlyConfigured('Staging requires DEBUG=False.')
if os.environ.get('ISURVIX_LOCAL_AI_ENABLED','False')!='False':
    raise ImproperlyConfigured('Hosted staging never starts local inference; use the outbound worker.')

_key_file=os.environ.get('DJANGO_SECRET_KEY_FILE','').strip()
_key=os.environ.get('DJANGO_SECRET_KEY','').strip()
if bool(_key_file)==bool(_key):
    raise ImproperlyConfigured('Configure exactly one private DJANGO_SECRET_KEY_FILE or DJANGO_SECRET_KEY.')
if _key_file:
    try:_key=Path(_key_file).read_text(encoding='utf-8').strip()
    except (OSError,UnicodeError):raise ImproperlyConfigured('The private staging secret file cannot be read.') from None
if len(_key)<50 or _key.startswith(('django-insecure-','change-me')):
    raise ImproperlyConfigured('Use a private production-strength staging secret; its value is not logged.')
SECRET_KEY=_key

DEBUG=False
ALLOWED_HOSTS=[x.strip().lower() for x in _required('DJANGO_ALLOWED_HOSTS').split(',')]
for _host in ALLOWED_HOSTS:
    if (not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',_host)
            or '.' not in _host or '..' in _host):
        raise ImproperlyConfigured('Use explicit staging DNS hostnames, without wildcard or URL syntax.')
    try:ipaddress.ip_address(_host)
    except ValueError:pass
    else:raise ImproperlyConfigured('Use an explicit staging DNS hostname, not an IP or loopback address.')

CSRF_TRUSTED_ORIGINS=[x.strip() for x in _required('DJANGO_CSRF_TRUSTED_ORIGINS').split(',')]
for _origin in CSRF_TRUSTED_ORIGINS:
    try:
        _parts=urlsplit(_origin);_port=_parts.port
    except ValueError:raise ImproperlyConfigured('Invalid staging HTTPS origin.') from None
    if (_parts.scheme!='https' or _parts.hostname not in ALLOWED_HOSTS or _parts.username or
            _parts.password or _parts.path or _parts.query or _parts.fragment):
        raise ImproperlyConfigured('Each CSRF origin must be HTTPS and match an allowed staging host.')

_data=Path(_required('ISURVIX_DATA_ROOT'))
if not _data.is_absolute():raise ImproperlyConfigured('ISURVIX_DATA_ROOT must be an absolute persistent path.')
STAGING_DATA_ROOT=_data.resolve()
if STAGING_DATA_ROOT==BASE_DIR or BASE_DIR in STAGING_DATA_ROOT.parents:  # noqa: F405
    raise ImproperlyConfigured('Keep persistent staging data outside the backend code directory.')
MEDIA_ROOT=STAGING_DATA_ROOT/'media'
STATIC_ROOT=STAGING_DATA_ROOT/'static'
FILE_UPLOAD_TEMP_DIR=str(STAGING_DATA_ROOT/'upload-tmp')
for _directory in [STAGING_DATA_ROOT,MEDIA_ROOT,STATIC_ROOT,Path(FILE_UPLOAD_TEMP_DIR)]:
    if not _directory.is_dir() or not os.access(_directory,os.W_OK):
        raise ImproperlyConfigured('Create writable persistent data/media/static/upload-tmp directories before startup.')
if _key_file and (Path(_key_file).resolve().is_relative_to(MEDIA_ROOT) or Path(_key_file).resolve().is_relative_to(STATIC_ROOT)):
    raise ImproperlyConfigured('Private secrets must not be stored in upload/static directories.')

ISURVIX_RELEASE_ID=_required('ISURVIX_RELEASE_ID')
if not re.fullmatch(r'[0-9a-f]{40}',ISURVIX_RELEASE_ID):
    raise ImproperlyConfigured('ISURVIX_RELEASE_ID must identify the exact reviewed 40-character commit.')
_release_file=Path(os.environ.get('ISURVIX_RELEASE_FILE',str(BASE_DIR.parent/'RELEASE')))  # noqa: F405
try:_baked_release=_release_file.read_text(encoding='ascii').strip()
except (OSError,UnicodeError):raise ImproperlyConfigured('The read-only baked release identity file is unavailable.') from None
if _baked_release!=ISURVIX_RELEASE_ID:
    raise ImproperlyConfigured('Configured release identity does not match the built image; refuse startup.')

DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':STAGING_DATA_ROOT/'database.sqlite3',
    'OPTIONS':{'timeout':30,'transaction_mode':'IMMEDIATE'},'ATOMIC_REQUESTS':False}}
if not DATABASES['default']['NAME'].is_file() and os.environ.get('ISURVIX_INITIALIZE_DATABASE')!='yes':
    raise ImproperlyConfigured('The persistent database is missing. Use the explicit one-off bootstrap/restore procedure, never an empty web install.')
LOCAL_AI_ENABLED=False
OLLAMA_BASE_URL='http://127.0.0.1:11434'
PHOTO_OLLAMA_BASE_URL=OLLAMA_BASE_URL
PHOTO_MAX_PER_SITE=500
FILE_UPLOAD_PERMISSIONS=0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o700
STORAGES={
    'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
    'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage',
                   'OPTIONS':{'file_permissions_mode':0o644,'directory_permissions_mode':0o755}},
}
SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
# Reuse existing invitation redaction and emit container logs without writing code.
LOGGING={
    'version':1,'disable_existing_loggers':False,
    'filters':{'redact_invitations':{'()':'core.governance_logging.RedactInvitations'}},
    'handlers':{'console':{'class':'logging.StreamHandler','filters':['redact_invitations']}},
    'root':{'handlers':['console'],'level':'INFO'},
    'loggers':{name:{'handlers':['console'],'level':'WARNING' if name=='django.request' else 'INFO','propagate':False}
               for name in ['django','django.request','django.server']},
}
