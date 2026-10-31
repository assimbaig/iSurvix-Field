"""Intake forms deliberately expose no account or company authority fields."""
import uuid
from django import forms
from .models import IndustryCatalog


class CompanyApplicationForm(forms.Form):
    request_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    name = forms.CharField(max_length=160, label='Company name')
    email = forms.EmailField(label='Company Admin email')
    industry = forms.ModelChoiceField(queryset=IndustryCatalog.objects.filter(is_active=True))


class CompanyApplicationActionForm(forms.Form):
    action = forms.ChoiceField(choices=[('approve', 'Approve application'), ('reject', 'Reject application'),
                                      ('provision', 'Provision company'), ('invite', 'Invite company Admin')])
    review_note = forms.CharField(required=False, max_length=4000)
