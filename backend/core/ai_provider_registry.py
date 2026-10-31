"""Parse operator-managed connection aliases without loading or exposing secrets."""
import json
import re
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def load_registry(raw):
    if not raw:
        return {}
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError()
                result[key] = value
            return result
        result = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(result, dict) or len(result) > 100:
            raise ValueError()
        for alias, entry in result.items():
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', alias) or not isinstance(entry, dict):
                raise ValueError()
            if set(entry) != {'endpoint', 'credential_env'}:
                raise ValueError()
            endpoint, credential = entry['endpoint'], entry['credential_env']
            if not isinstance(endpoint, str) or len(endpoint) > 500 or not isinstance(credential, str):
                raise ValueError()
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', credential):
                raise ValueError()
            url = urlsplit(endpoint)
            if (url.scheme != 'https' or not url.hostname or url.username or url.password
                    or url.query or url.fragment or url.path not in ('', '/') or url.port == 0
                    or any(ord(c) < 33 for c in endpoint)):
                raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise ImproperlyConfigured('Invalid operator AI provider registry. Use approved HTTPS connection aliases and credential environment references only.') from None
