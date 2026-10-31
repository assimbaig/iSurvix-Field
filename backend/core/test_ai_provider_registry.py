"""Operator registry startup validation is explicit and does not reveal input."""
import json
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class ProviderRegistryTests(SimpleTestCase):
    def load(self, raw):
        from core.ai_provider_registry import load_registry
        return load_registry(raw)

    def test_no_configuration_preserves_local_only_default(self):
        self.assertEqual(self.load(''), {})

    def test_operator_alias_keeps_credentials_as_references(self):
        value = {'approved': {'endpoint': 'https://inference.example.org', 'credential_env': 'ISURVIX_PROVIDER_TOKEN'}}
        self.assertEqual(self.load(json.dumps(value)), value)

    def test_malformed_and_unexpected_config_fail_closed_without_echo(self):
        canary = 'private-canary-never-echo'
        for value in (canary, '[]', '{"bad alias": {}}', json.dumps({'ok': {'endpoint': 'https://example.org', 'api_key': canary}})):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ImproperlyConfigured) as error:
                self.load(value)
            self.assertNotIn(canary, str(error.exception))

    def test_embedded_credentials_queries_and_plain_http_are_rejected(self):
        for endpoint in ('http://example.org', 'https://name:secret@example.org', 'https://example.org?key=private', 'https://example.org/#private'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ImproperlyConfigured):
                self.load(json.dumps({'ok': {'endpoint': endpoint, 'credential_env': 'PRIVATE_TOKEN'}}))
