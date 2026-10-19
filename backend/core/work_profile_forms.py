from django import forms
from .work_profile_models import WorkProfile,ProfessionalExperience

class WorkProfileForm(forms.ModelForm):
    class Meta:
        model=WorkProfile
        fields=['display_name','headline','bio','published']
        labels={'display_name':'Professional display name','bio':'Professional introduction','published':'Publish my professional profile to eligible people on active shared projects'}
        widgets={'bio':forms.Textarea(attrs={'rows':5})}
        help_texts={'published':'Off by default. Clients can see published staff profiles only while both accounts retain active access to a shared project. Authentication and contact details are never included.'}

class ProfessionalExperienceForm(forms.ModelForm):
    class Meta:
        model=ProfessionalExperience
        fields=['organization','job_title','start_date','end_date','is_current','summary','qualifications']
        labels={'is_current':'I currently work in this role','qualifications':'Relevant qualifications (self-reported)'}
        widgets={'start_date':forms.DateInput(attrs={'type':'date'}),'end_date':forms.DateInput(attrs={'type':'date'}),'summary':forms.Textarea(attrs={'rows':4}),'qualifications':forms.Textarea(attrs={'rows':3})}
    def clean(self):
        data=super().clean()
        start,end=data.get('start_date'),data.get('end_date')
        if start and end and end<start:self.add_error('end_date','End date must be on or after the start date.')
        if data.get('is_current') and end:self.add_error('end_date','Leave end date empty for a current role.')
        return data
