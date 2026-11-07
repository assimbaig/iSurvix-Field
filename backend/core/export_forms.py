import uuid
from django import forms
from .export_service import catalog,_projects

class DataExportForm(forms.Form):
 section=forms.ChoiceField(label='Data section')
 project=forms.ModelChoiceField(queryset=None,required=False,empty_label='All my permitted projects')
 request_key=forms.UUIDField(widget=forms.HiddenInput)
 def __init__(self,*args,actor,**kwargs):
  super().__init__(*args,**kwargs)
  self.fields['section'].choices=list(catalog(actor).items())
  self.fields['project'].queryset=_projects(actor,{}).order_by('name')
  self.fields['request_key'].initial=uuid.uuid4()
