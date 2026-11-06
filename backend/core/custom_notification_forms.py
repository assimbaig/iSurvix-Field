"""Company notification settings use fixed plaintext placeholders, never executable templates."""
from datetime import time
from django import forms
from .custom_notifications import KINDS,validate_templates

class NotificationSettingsForm(forms.Form):
    version=forms.IntegerField(min_value=0,widget=forms.HiddenInput)
    kind=forms.ChoiceField(choices=list(KINDS.items()),widget=forms.HiddenInput,label='Notification action')
    use_default=forms.BooleanField(required=False,label='Use the standard message for this action')
    subject=forms.CharField(required=False,max_length=180,label='Custom subject')
    body=forms.CharField(required=False,max_length=12000,widget=forms.Textarea(attrs={'rows':7}),label='Custom plain-text message')
    combined_daily_enabled=forms.BooleanField(required=False,label='Send one combined daily notification report across projects')
    daily_time=forms.TimeField(initial=time(18),widget=forms.TimeInput(attrs={'type':'time'}),label='Business-day cut-off time')
    timezone_name=forms.CharField(max_length=80,initial='Asia/Riyadh',label='IANA time zone (for example Asia/Riyadh or Asia/Karachi)')
    def clean(self):
        data=super().clean()
        if not data.get('use_default') and data.get('kind'):
            try:validate_templates({data['kind']:{'subject':data.get('subject',''),'body':data.get('body','')}})
            except forms.ValidationError as error:self.add_error(None,error)
        return data
