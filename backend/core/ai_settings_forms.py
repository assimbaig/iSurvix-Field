"""Public AI configuration contains policy and server-managed aliases, never keys."""
import re
from django import forms
from django.conf import settings


def provider_aliases():
    registry = getattr(settings, 'AI_PROVIDER_REGISTRY', {})
    if not isinstance(registry, dict):
        return []
    return sorted(key for key in registry if isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', key))


class AISettingsForm(forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    enabled = forms.BooleanField(required=False, label='Enable configured routing')
    primary_provider = forms.ChoiceField(choices=[('local', 'Local Ollama'), ('https_ollama', 'Configured HTTPS provider')], label='Primary route')
    local_model = forms.CharField(max_length=160, initial='qwen3.5:4b', label='Local model')
    api_model = forms.CharField(max_length=160, required=False, label='HTTPS provider model')
    api_endpoint = forms.ChoiceField(required=False, label='Provider connection')
    allow_external_evidence = forms.BooleanField(required=False, label='Allow survey evidence to leave this computer through the configured provider')
    fallback_enabled = forms.BooleanField(required=False, label='Allow fallback to the other configured route')
    daily_request_limit = forms.IntegerField(min_value=0, max_value=1000000, initial=2000, label='Daily provider-attempt limit')
    request_timeout = forms.IntegerField(min_value=5, max_value=600, initial=120, label='Request timeout (seconds)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['api_endpoint'].choices = [('', 'No HTTPS provider selected')] + [(key, key) for key in provider_aliases()]

    def clean(self):
        data = super().clean()
        uses_external = data.get('primary_provider') == 'https_ollama' or data.get('fallback_enabled')
        if uses_external:
            if not data.get('allow_external_evidence'):
                self.add_error('allow_external_evidence', 'Consent to external evidence processing is required for this route or fallback.')
            if not data.get('api_endpoint'):
                self.add_error('api_endpoint', 'Select a server-configured provider connection.')
            if not data.get('api_model'):
                self.add_error('api_model', 'Enter the model configured at that provider.')
        return data
