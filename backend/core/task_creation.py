"""Single and table-based task entry using the existing assignment/review services."""
import json
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .access import accessible_projects,users_for_project
from .models import Profile,AssignmentIntakeBatch
from .governance_forms import AssignmentForm
from .governance_views import guarded_write,lock_governance
from .field_intake_views import assign_guard
from .field_intake_service import (general_fields,validated_site_basics,create_assignment,
                                  preview_rows,commit_batch,CONTEXT_COLUMNS,BASIC_SITE_COLUMNS)


def project_workflow(project):
    return 'Engineer → QA Engineer → Team Lead' + (' → Client' if project.review_layers==4 else ' → Client if configured' if project.review_layers is None else '')


class SiteTaskForm(AssignmentForm):
    site_name=forms.CharField(max_length=200,required=False,label='Site name')
    address=forms.CharField(max_length=1000,required=False,label='Site address')
    city=forms.CharField(max_length=200,required=False)
    region=forms.CharField(max_length=200,required=False)

    def __init__(self,*args,actor,project,bulk=False,**kwargs):
        self.bulk=bulk
        super().__init__(*args,actor=actor,**kwargs)
        self.fields['project'].widget=forms.HiddenInput();self.initial['project']=project.pk
        self.fields['general_info'].widget=forms.HiddenInput()
        self.fields['description'].required=False
        self.fields['description'].widget=forms.Textarea(attrs={'rows':2})
        self.fields['description'].label='Work instructions'
        self.fields['site_id'].label='Site ID'
        self.fields['coordinate_source'].required=True
        self.fields['coordinate_source'].label='Coordinate source'
        self.fields['coordinate_crs'].required=True
        self.fields['coordinate_crs'].label='Coordinate datum / CRS'
        self.fields['coordinate_crs'].help_text='For example, EPSG:4326 only if your source uses WGS84.'
        roles={'engineer':Profile.Roles.ENGINEER,'quality_reviewer':Profile.Roles.QUALITY_ENGINEER,
               'l2_reviewer':Profile.Roles.QUALITY_ENGINEER,'l3_approver':Profile.Roles.TEAM_LEAD,
               'customer_reviewer':Profile.Roles.CLIENT}
        for name,role in roles.items():
            people=users_for_project(project,{role}).filter(is_active=True).order_by('username')
            self.fields[name].queryset=people
            if people.count()==1:self.initial[name]=people.first().pk
        self.fields['l2_reviewer'].label='QA Engineer'
        self.fields['quality_reviewer'].label='QA Engineer'
        self.fields['l3_approver'].label='Team Lead'
        self.fields['customer_reviewer'].label='Client reviewer'
        from .industry_service import industry_family
        family=industry_family(project)
        self.fields['workflow_type'].choices=[item for item in self.fields['workflow_type'].choices if not item[0] or item[0].startswith(family)]
        self.fields['workflow_type'].label='Activity'
        from .standard_checklist_service import wizard_metadata,standard_metadata
        metadata=(wizard_metadata(project.checklist_template.definition) or standard_metadata(project.checklist_template.definition)) if project.checklist_template_id else None
        default_activity=metadata['workflow_type'] if metadata else 'construction_inspection' if family=='construction' else 'telecom_survey'
        self.initial['workflow_type']=default_activity
        if metadata:self.fields['workflow_type'].choices=[item for item in self.fields['workflow_type'].choices if item[0]==default_activity]
        independent=project.review_layers in (3,4) or default_activity!='telecom_survey'
        from .workflow_service import configured_client_review
        customer_required=project.review_layers==4 or project.review_layers is None and independent and configured_client_review(project.pk)

        self.initial['l3_approver']=actor.pk if actor.profile.role==Profile.Roles.TEAM_LEAD and users_for_project(project,{Profile.Roles.TEAM_LEAD}).filter(pk=actor.pk).exists() else self.initial.get('l3_approver')
        for name in ('governance_mode','client_review_required','review_reason'):
            self.fields[name].widget=forms.HiddenInput()
        self.initial['governance_mode']='independent' if independent else 'legacy'
        self.initial['client_review_required']='required' if customer_required else 'not_required' if independent else ''
        self.reviewer_names=['engineer','l2_reviewer','l3_approver'] if independent else ['engineer','quality_reviewer']
        if customer_required:self.reviewer_names.append('customer_reviewer')
        for name in self.reviewer_names:self.fields[name].required=True
        self.extra_names=[]
        if project.checklist_template_id:
            for fid,field in general_fields(project.checklist_template.definition).items():
                if field.get('system'):continue
                name='general__'+fid
                if field['type']=='select':control=forms.ChoiceField(choices=[('','Complete later'),*[(v,v) for v in field['options']]],required=False)
                else:control=forms.CharField(required=False,max_length=10000,widget=forms.Textarea(attrs={'rows':2}) if field['type']=='textarea' else forms.TextInput())
                control.label=field['label'];control.help_text=field.get('description','')
                self.fields[name]=control;self.extra_names.append(name)
        if bulk:
            for name in ('site_id','latitude','longitude'):self.fields[name].required=False

    def clean_site_id(self):
        if self.bulk and not self.cleaned_data.get('site_id'):return ''
        return super().clean_site_id()

    def clean(self):
        for key in ('workflow_type','governance_mode','client_review_required'):
            if not self.cleaned_data.get(key):self.cleaned_data[key]=self.initial.get(key,'')
        values={name[9:]:self.cleaned_data[name] for name in self.extra_names if self.cleaned_data.get(name)}
        self.cleaned_data['general_info']={**(self.cleaned_data.get('general_info') or {}),**values}
        data=super().clean()
        data['site_information']=validated_site_basics(data)
        data['description']=data.get('description') or 'Site survey / inspection'
        return data


def return_location(request):
    value=request.POST.get('return_to') or request.GET.get('return_to','')
    route=reverse('task_explorer')
    return value if value==route or value.startswith(route+'?') else route


@login_required(login_url='/login/')
@require_http_methods(['GET','POST'])
@never_cache
@guarded_write
def create(request):
    assign_guard(request.user)
    projects=accessible_projects(request.user).select_related('checklist_template').order_by('name')
    value=request.POST.get('project') or request.GET.get('project','')
    project=get_object_or_404(projects,pk=int(value)) if value.isascii() and value.isdigit() and len(value)<=19 else projects.first() if not value or value=='all' else get_object_or_404(projects,pk=0)
    mode=request.POST.get('mode') or request.GET.get('mode','single')
    mode='bulk' if mode=='bulk' else 'single'
    form=SiteTaskForm(request.POST if request.method=='POST' and request.POST.get('action')!='commit' else None,actor=request.user,project=project,bulk=mode=='bulk') if project else None
    batch=None;error='';status=200;entered=[]
    if request.method=='POST':
        try:
            if not project:raise ValidationError('Create a project and assign its published checklist first.')
            with transaction.atomic():
                lock_governance(request.user);assign_guard(request.user)
                action=request.POST.get('action')
                if action=='commit':
                    batch_id=request.POST.get('batch_id','')
                    if not batch_id.isascii() or not batch_id.isdigit() or len(batch_id)>19:raise ValidationError('Choose a valid site preview.')
                    batch=get_object_or_404(AssignmentIntakeBatch.objects.select_for_update(),pk=int(batch_id))
                    results=commit_batch(request.user,batch)
                    messages.success(request,f'{len(results)} site tasks created with their project workflow and site information.')
                    return redirect(return_location(request))
                if mode=='bulk':
                    raw=request.POST.get('site_rows','[]')
                    if len(raw)>500000:raise ValidationError('Enter at most 200 site rows.')
                    entered=json.loads(raw)
                    if not isinstance(entered,list) or not 1<=len(entered)<=200:
                        entered=[];raise ValidationError('Enter between 1 and 200 sites.')
                    allowed={'site_id','latitude','longitude','description',*BASIC_SITE_COLUMNS}
                    if any(not isinstance(row,dict) or set(row)-allowed or any(not isinstance(v,str) for v in row.values()) for row in entered):
                        entered=[];raise ValidationError('Site rows contain unsupported fields or values.')
                if form.is_valid():
                    if mode=='single' and action=='create':
                        work=create_assignment(request.user,form.cleaned_data,{'kind':'single_task_form'})
                        messages.success(request,f'Task {work.site_id} created. Its saved checklist includes the recorded site information.')
                        return redirect(return_location(request))
                    if mode=='bulk' and action=='preview':
                        data=form.cleaned_data
                        common={key:getattr(data.get(key),'pk',data.get(key)) or '' for key in CONTEXT_COLUMNS}
                        common.update(project=project.pk,engineer=data['engineer'].pk,description=data['description'],general_info=data['general_info'])
                        rows=[{**common,**{key:data.get(key,'') for key in BASIC_SITE_COLUMNS},**row,'description':row.get('description') or data['description']} for row in entered]
                        batch=preview_rows(request.user,rows,str(project.pk),filename='Entered site table',raw=raw.encode(),entry_mode='bulk_sites')
                        status=400 if batch.errors else 200
                    else:raise ValidationError('Choose Create task or Preview sites.')
                else:status=400
        except (ValidationError,ValueError,TypeError) as exc:
            error='; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Enter valid site rows.'
            status=409 if request.POST.get('action')=='commit' else 400
    return render(request,'dashboards/task_create.html',{'active_view':'tasks','projects':projects,'project':project,
        'task_form':form,'setup_fields':[form[n] for n in ['workflow_type',*(form.reviewer_names if form else []),'description','coordinate_source','coordinate_crs','asset_reference']] if form else [],
        'extra_fields':[form[n] for n in form.extra_names] if form else [],'mode':mode,'entered_sites':entered,'batch':batch,'error':error,
        'return_to':return_location(request),'workflow':project_workflow(project) if project else '',
        'selected_project_id':str(project.pk) if project else '', 'selected_industry':project.industry if project else '',
        'ready':bool(project and project.checklist_template_id and project.checklist_template.published and not project.checklist_template.disabled)},status=status)
