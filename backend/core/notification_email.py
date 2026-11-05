"""Private Microsoft Graph transport for the fixed iField notification sender.

Only Graph's 202 response means the message was accepted for processing. It
does not establish delivery to the recipient's inbox. An ambiguous send outcome
must not be automatically retried: Graph sendMail has no idempotency guarantee.
This module never logs credentials, bearer tokens, message bodies or responses.
"""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .http_deadline import request as bounded_request, RequestError, ResponseTooLarge


SENDER = 'ifield.notify@isurvix.com'
DISPLAY_NAME = 'iSurvix iField Notifications'
TOKEN_URL_TEMPLATE = 'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'
SEND_MAIL_URL = 'https://graph.microsoft.com/v1.0/users/ifield.notify%40isurvix.com/sendMail'
_TIMEOUT = (5, 15)
_REQUEST_DEADLINE = 20
_MAX_CONFIG_BYTES = 16 * 1024
_MAX_TOKEN_BYTES = 64 * 1024
_MAX_BODY_BYTES = 64 * 1024
_BEARER = re.compile(r'[A-Za-z0-9._~+/-]+=*\Z')


class NotificationEmailError(Exception):
    """Safe state-machine input; never pass raw provider/requests errors here."""

    def __init__(self, code, *, retryable=False, uncertain=False):
        self.code = code
        self.retryable = bool(retryable)
        self.uncertain = bool(uncertain)
        super().__init__('Notification email: ' + code.replace('_', ' ') + '.')


@dataclass(frozen=True)
class GraphMailConfig:
    tenant_id: str
    client_id: str
    client_secret: str = field(repr=False)


def _validated_config(value):
    if isinstance(value, GraphMailConfig):
        value = {key: getattr(value, key) for key in ('tenant_id', 'client_id', 'client_secret')}
    try:
        if not isinstance(value, dict) or set(value) != {'tenant_id', 'client_id', 'client_secret'}:
            raise ValueError
        identities = []
        for key in ('tenant_id', 'client_id'):
            if not isinstance(value[key], str):
                raise ValueError
            identifier = UUID(value[key])
            if identifier.int == 0:
                raise ValueError
            identities.append(str(identifier))
        secret = value['client_secret']
        if (not isinstance(secret, str) or not secret.strip() or len(secret) > 8192
                or any(character in secret for character in '\r\n\x00')):
            raise ValueError
        return GraphMailConfig(*identities, secret)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise NotificationEmailError('configuration_invalid') from None


def _json_without_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate configuration key.')
        value[key] = item
    return value


def load_config():
    """Read one bounded private file; no environment-secret or network fallback.

    On Windows the operator must provision a private ACL for this file. POSIX
    permissions are verified where available. The path and its ancestors cannot
    be links/junctions, and file identity is rechecked after opening it.
    """
    configured = getattr(settings, 'NOTIFICATION_EMAIL_CREDENTIALS_FILE', '')
    if not configured:
        raise NotificationEmailError('configuration_missing')
    try:
        path = Path(configured)
        if not path.is_absolute():
            raise ValueError
        for part in (path, *path.parents):
            if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
                raise ValueError
        resolved = path.resolve(strict=True)
        for setting_name in ('MEDIA_ROOT', 'STATIC_ROOT'):
            root = getattr(settings, setting_name, None)
            if root and resolved.is_relative_to(Path(root).resolve()):
                raise ValueError
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, 'rb') as handle:
            opened = os.fstat(handle.fileno())
            if ((before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                    or not stat.S_ISREG(opened.st_mode)
                    or opened.st_size > _MAX_CONFIG_BYTES):
                raise ValueError
            if os.name != 'nt' and stat.S_IMODE(opened.st_mode) & 0o077:
                raise ValueError
            raw = handle.read(_MAX_CONFIG_BYTES + 1)
        if len(raw) > _MAX_CONFIG_BYTES:
            raise ValueError
        parsed = json.loads(raw.decode('utf-8'), object_pairs_hook=_json_without_duplicate_keys)
        return _validated_config(parsed)
    except NotificationEmailError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError):
        raise NotificationEmailError('configuration_invalid') from None


def _token_json(raw):
    if len(raw) > _MAX_TOKEN_BYTES:
        raise ValueError
    data = json.loads(raw.decode('utf-8'))
    if not isinstance(data, dict):
        raise ValueError
    token = data.get('access_token')
    expires = data.get('expires_in')
    if (not isinstance(token, str) or not 1 <= len(token) <= 16384
            or not _BEARER.fullmatch(token)
            or str(data.get('token_type', '')).lower() != 'bearer'
            or type(expires) is not int or not 1 <= expires <= 86400):
        raise ValueError
    return token


class GraphMailClient:
    """A single bounded token exchange and send; no implicit request retries."""

    def __init__(self, config=None):
        self._config = load_config() if config is None else _validated_config(config)

    def _token(self):
        config = self._config
        try:
            response = bounded_request('POST', TOKEN_URL_TEMPLATE.format(tenant_id=config.tenant_id), data={
                'grant_type': 'client_credentials', 'client_id': config.client_id,
                'client_secret': config.client_secret, 'scope': 'https://graph.microsoft.com/.default',
            }, headers={'Accept': 'application/json'}, timeout=_TIMEOUT,
                total_timeout=_REQUEST_DEADLINE, max_bytes=_MAX_TOKEN_BYTES)
        except ResponseTooLarge:
            raise NotificationEmailError('authentication_invalid_response') from None
        except RequestError:
            raise NotificationEmailError('authentication_unavailable', retryable=True) from None
        if response.status_code != 200:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise NotificationEmailError('authentication_rejected', retryable=retryable)
        try:
            return _token_json(response.body)
        except (ValueError, TypeError, UnicodeError):
            raise NotificationEmailError('authentication_invalid_response') from None

    def send(self, recipient, subject, body):
        try:
            if not isinstance(recipient, str) or len(recipient) > 254 or any(c in recipient for c in '\r\n\x00'):
                raise ValueError
            validate_email(recipient)
            if (not isinstance(subject, str) or not 1 <= len(subject) <= 200
                    or any(c in subject for c in '\r\n\x00') or not isinstance(body, str)
                    or len(body.encode('utf-8')) > _MAX_BODY_BYTES):
                raise ValueError
        except (ValueError, TypeError, ValidationError, UnicodeError):
            raise NotificationEmailError('message_invalid') from None

        token = self._token()
        payload = {'message': {
            'from': {'emailAddress': {'address': SENDER, 'name': DISPLAY_NAME}},
            'toRecipients': [{'emailAddress': {'address': recipient}}],
            'subject': subject, 'body': {'contentType': 'Text', 'content': body},
        }, 'saveToSentItems': True}
        try:
            response = bounded_request('POST', SEND_MAIL_URL, json=payload,
                headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'},
                timeout=_TIMEOUT, total_timeout=_REQUEST_DEADLINE, max_bytes=0, read_body=False)
        except RequestError:
            # The POST may already have been processed when the connection
            # failed. Repeating it can send a second bearer invitation.
            raise NotificationEmailError('send_outcome_unknown', uncertain=True) from None
        status = response.status_code
        if status == 202:
            return None
        if status == 429:
            raise NotificationEmailError('send_rate_limited', retryable=True)
        if status == 401:
            raise NotificationEmailError('send_not_authorized', retryable=True)
        if status == 403:
            raise NotificationEmailError('send_not_authorized')
        if 200 <= status < 300 or status >= 500:
            raise NotificationEmailError('send_outcome_unknown', uncertain=True)
        raise NotificationEmailError('send_rejected')
