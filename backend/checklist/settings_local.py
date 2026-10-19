"""Loopback-only development settings; production settings stay unchanged."""
import os
import secrets
from pathlib import Path

STATE = Path(__file__).resolve().parents[2] / '.local'
STATE.mkdir(exist_ok=True)
key_file = STATE / 'django-secret'
if not key_file.exists():
    try:
        with key_file.open('x', encoding='utf-8') as output:
            output.write(secrets.token_urlsafe(64))
        key_file.chmod(0o600)
    except FileExistsError:
        pass
os.environ['DJANGO_SECRET_KEY'] = key_file.read_text(encoding='utf-8').strip()
from .settings import *  # noqa: F403,E402

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]']
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None
ROOT_URLCONF = 'checklist.urls_local'
DATABASES['default']['NAME'] = STATE / 'survey.sqlite3'
# Reserve the sole SQLite writer at the start of short atomic blocks, avoiding
# deferred read-to-write upgrades. Model inference remains outside transactions.
DATABASES['default']['OPTIONS'] = {**DATABASES['default'].get('OPTIONS', {}), 'timeout': 30, 'transaction_mode': 'IMMEDIATE'}
DATABASES['default']['ATOMIC_REQUESTS'] = False
MEDIA_ROOT = STATE / 'media'
MEDIA_ROOT.mkdir(exist_ok=True)
FILE_UPLOAD_TEMP_DIR = STATE / 'upload-tmp'
FILE_UPLOAD_TEMP_DIR.mkdir(exist_ok=True)
LOGGING['handlers']['file']['filename'] = STATE / 'app.log'
LOCAL_AI_ENABLED = True
PHOTO_MAX_PER_SITE = 500
OLLAMA_BASE_URL = os.environ.get('ISURVIX_OLLAMA_URL', 'http://127.0.0.1:11434')
# Photo inference can run independently of the interactive assistant.
PHOTO_OLLAMA_BASE_URL = os.environ.get('ISURVIX_PHOTO_OLLAMA_URL', OLLAMA_BASE_URL)
OLLAMA_MODEL = os.environ.get('ISURVIX_AI_MODEL', 'qwen3.5:4b')
OLLAMA_TIMEOUT = 180
MIDDLEWARE.insert(0, 'core.local_ai.LoopbackOnlyMiddleware')
TEMPLATES[0]['OPTIONS']['context_processors'].append('core.local_ai.local_context')
