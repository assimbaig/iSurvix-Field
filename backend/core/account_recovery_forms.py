from django import forms
from django.contrib.auth.forms import SetPasswordForm


class RecoveryRequestForm(forms.Form):
    email=forms.EmailField(label='Registered email address',max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete':'email'}))


class RecoveryPasswordForm(SetPasswordForm):
    """Reuse the configured Django password validators and password widgets."""
