"""Read-only operational task index; database filters and pagination precede stage checks."""
import csv
import re
from urllib.parse import urlencode
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q,F,Value,CharField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse,NoReverseMatch
from django.views.decorators.http import require_GET
from .models import Checklist,WorkAssignment,Profile,IndustryCatalog
from .access import accessible_projects,role_for,is_super_admin

FIELDS=['task_pk','task_site','task_project_id','task_project','task_user_id','task_user','task_status','task_module','task_created','task_updated','task_description','task_kind']
SORTS={'updated':('-task_updated','task_kind','task_pk'),'oldest':('task_created','task_kind','task_pk'),'site':('task_site','task_kind','task_pk'),'project':('task_project','task_site','task_kind','task_pk'),'status':('task_status','task_site','task_kind','task_pk'),'site_desc':('-task_site','task_kind','task_pk'),'project_desc':('-task_project','task_site','task_pk'),'status_desc':('-task_status','task_site','task_pk'),'module':('task_module','task_site','task_pk'),'module_desc':('-task_module','task_site','task_pk')}

def scopes(user):
    role=role_for(user)
    if is_super_admin(user) or role not in {Profile.Roles.ADMIN,Profile.Roles.ENGINEER,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.PROJECT_MANAGER,Profile.Roles.CLIENT}:
        raise PermissionDenied('Operational tasks require an assigned project role.')
    projects=accessible_projects(user)
    checklists=Checklist.objects.filter(project__in=projects)
    legacy=Q(governance_mode='legacy')
    if role==Profile.Roles.ENGINEER:checklists=checklists.filter(user=user)
    elif role==Profile.Roles.CLIENT:
        from .access import client_checklist_visibility
        checklists=checklists.filter(client_checklist_visibility(user)).distinct()
    elif role==Profile.Roles.TEAM_LEAD:checklists=checklists.filter(legacy|Q(review_policy__workflow_version=1,review_policy__l2_reviewer=user)|Q(review_policy__workflow_version=2,review_policy__l3_approver=user))
    elif role==Profile.Roles.QUALITY_ENGINEER:checklists=checklists.filter(Q(governance_mode='legacy',quality_reviewer=user)|Q(review_policy__workflow_version=2,review_policy__l2_reviewer=user))
    elif role==Profile.Roles.PROJECT_MANAGER:checklists=checklists.filter(governance_mode='independent',review_policy__workflow_version=1,review_policy__l3_approver=user)
    assignments=WorkAssignment.objects.filter(project__in=projects,checklist__isnull=True)
    if role==Profile.Roles.ENGINEER:assignments=assignments.filter(assigned_to=user)
    elif role not in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD}:assignments=assignments.none()
    return projects,checklists,assignments

class TaskFilters(forms.Form):
    q=forms.CharField(required=False,max_length=200,label='Search',widget=forms.TextInput(attrs={'placeholder':'Site, project or description'}))
    industry=forms.ChoiceField(required=False)
    project=forms.ModelChoiceField(queryset=Checklist.objects.none(),required=False)
    status=forms.ChoiceField(required=False)
    assignee=forms.ModelChoiceField(queryset=User.objects.none(),required=False)
    date_from=forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}),label='Created from')
    date_to=forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}),label='Created through')
    module=forms.ChoiceField(required=False,choices=[('','All modules'),*Checklist.WorkflowType.choices,('unclassified','Unclassified assignment')])
    sort=forms.ChoiceField(required=False,choices=[('updated','Recently updated'),('oldest','Oldest first'),('site','Site ID'),('project','Project'),('status','Stored status'),('site_desc','Site ID descending'),('project_desc','Project descending'),('status_desc','Status descending'),('module','Module'),('module_desc','Module descending')])
    def __init__(self,*args,projects,checklists,assignments,client=False,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['project'].queryset=projects.order_by('name')
        self.fields['industry'].choices=[('','All assigned industries'),*IndustryCatalog.objects.filter(code__in=projects.values_list('industry',flat=True)).values_list('code','name')]
        statuses=dict([*Checklist.Status.choices,*WorkAssignment.Status.choices])
        self.fields['status'].choices=[('','All stored statuses'),*statuses.items()]
        from .industry_service import industry_family
        industries={industry_family(code) for code in projects.values_list('industry',flat=True)}
        modules=[choice for choice in Checklist.WorkflowType.choices if choice[0].startswith('telecom') and 'telecom' in industries or choice[0].startswith('construction') and 'construction' in industries]
        self.fields['module'].choices=[('','All modules'),*modules,('unclassified','Unclassified assignment')]
        self.fields['assignee'].queryset=User.objects.filter(Q(pk__in=checklists.values('user_id'))|Q(pk__in=assignments.values('assigned_to_id'))).order_by('username')
        if client:self.fields.pop('assignee')
    def clean(self):
        data=super().clean()
        if data.get('date_from') and data.get('date_to') and data['date_from']>data['date_to']:self.add_error('date_to','Choose an end date on or after the start date.')
        return data

def filtered_rows(checklists,assignments,data,client=False):
    checklists=checklists.order_by().annotate(task_pk=F('pk'),task_site=F('site_id'),task_project_id=F('project_id'),task_project=F('project__name'),task_user_id=F('user_id'),task_user=F('user__username'),task_status=F('status'),task_module=F('workflow_type'),task_created=F('created_at'),task_updated=F('updated_at'),task_description=Value('',output_field=CharField()) if client else Coalesce('work_assignment__description',Value(''),output_field=CharField()),task_kind=Value('checklist',output_field=CharField()))
    assignments=assignments.order_by().annotate(task_pk=F('pk'),task_site=F('site_id'),task_project_id=F('project_id'),task_project=F('project__name'),task_user_id=F('assigned_to_id'),task_user=F('assigned_to__username'),task_status=F('status'),task_module=Value('',output_field=CharField()),task_created=F('created_at'),task_updated=F('created_at'),task_description=F('description'),task_kind=Value('assignment',output_field=CharField()))
    def apply(query):
        if data.get('industry'):query=query.filter(project__industry=data['industry'])
        if data.get('q'):
            term=data['q'].strip()
            search=Q(task_site__icontains=term)|Q(task_project__icontains=term)|Q(task_description__icontains=term)
            if not client:search|=Q(task_user__icontains=term)
            task_id=re.fullmatch(r'#?([CAca]?)([0-9]+)',term)
            if task_id and len(task_id[2])<=19 and int(task_id[2])<=9223372036854775807:
                identity=Q(task_pk=int(task_id[2]))
                if task_id[1]:identity&=Q(task_kind='checklist' if task_id[1].upper()=='C' else 'assignment')
                search|=identity
            query=query.filter(search)
        if data.get('_selected'):
            identities=Q(pk__in=[])
            for kind,pk in data['_selected']:identities|=Q(task_kind=kind,task_pk=pk)
            query=query.filter(identities)
        for key,column in [('project','task_project_id'),('assignee','task_user_id'),('status','task_status')]:
            if data.get(key):query=query.filter(**{column:getattr(data[key],'pk',data[key])})
        if data.get('module'):query=query.filter(task_module='' if data['module']=='unclassified' else data['module'])
        if data.get('date_from'):query=query.filter(task_created__date__gte=data['date_from'])
        if data.get('date_to'):query=query.filter(task_created__date__lte=data['date_to'])
        return query.values(*FIELDS)
    return apply(checklists).union(apply(assignments)).order_by(*SORTS[data.get('sort') or 'updated'])

def csv_cell(value):
    text=str(value if value is not None else '')
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text

@login_required(login_url='/login/')
@require_GET
def explorer(request):
    projects,checklists,assignments=scopes(request.user)
    client=role_for(request.user)==Profile.Roles.CLIENT
    if client and request.GET.get('assignee'):raise PermissionDenied('Client task views do not expose personnel filters.')
    form_data=request.GET.copy()
    if form_data.get('project')=='all':form_data['project']=''
    form=TaskFilters(form_data,projects=projects,checklists=checklists,assignments=assignments,client=client)
    valid=form.is_valid()
    data=dict(form.cleaned_data) if valid else {}
    if request.GET.get('selected'):
        keys=request.GET['selected'].split(',')
        if len(keys)>100 or any(not re.fullmatch(r'[CA][0-9]{1,19}',key) or int(key[1:])>9223372036854775807 for key in keys):return HttpResponse('Choose up to100 task IDs for selected export.',status=400)
        if request.GET.get('export')=='csv':data['_selected']=[('checklist' if key[0]=='C' else 'assignment',int(key[1:])) for key in keys]
    rows=filtered_rows(checklists,assignments,data,client) if valid else []
    query=request.GET.copy();query.pop('export',None);query.pop('selected',None);query.pop('page',None)
    export_query=query.copy();export_query['export']='csv'
    if request.GET.get('export')=='csv':
        if not valid:return HttpResponse('Correct the task filters before exporting.',status=400)
        if rows.count()>10000:return HttpResponse('More than10000 tasks match. Narrow the filters before exporting.',status=400)
        response=HttpResponse(content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="isurvix-tasks.csv"'
        writer=csv.writer(response);writer.writerow(['Site ID','Project','Stored status','Module','Assigned Engineer','Created','Updated','Description'])
        for row in rows.iterator():writer.writerow([csv_cell(row[key]) for key in ['task_site','task_project','task_status','task_module']]+['' if client else csv_cell(row['task_user'])]+[csv_cell(row[key]) for key in ['task_created','task_updated','task_description']])
        response['Cache-Control']='private, no-store'
        return response
    page=Paginator(rows,25).get_page(request.GET.get('page'))
    ids=[row['task_pk'] for row in page if row['task_kind']=='checklist']
    objects={c.pk:c for c in checklists.filter(pk__in=ids).select_related('project','review_policy__current_revision','work_assignment')}
    back=reverse('task_explorer')+('?' + request.GET.urlencode() if request.GET else '')
    for row in page:
        c=objects.get(row['task_pk']) if row['task_kind']=='checklist' else None
        if c:
            row['stage']=c.workflow_label
            route='roadmap_activity' if c.governance_mode=='independent' else 'custom_checklist' if c.schema_snapshot else 'checklist_detail'
            row['review_url']=reverse(route,args=[c.pk])+'?'+urlencode({'return_to':back})
            row['url']=row['review_url']
            if c.schema_snapshot:
                try:row['url']=reverse('photo_workspace',args=[c.pk])+'?'+urlencode({'return_to':back})
                except NoReverseMatch:pass
        else:
            row['stage']=dict(WorkAssignment.Status.choices).get(row['task_status'],row['task_status'])
            row['url']=''
        row['key']=('C' if row['task_kind']=='checklist' else 'A')+str(row['task_pk'])
        row['module_label']=dict(Checklist.WorkflowType.choices).get(row['task_module'],'Unclassified assignment')
    def filter_link(**changes):
        parameters=query.copy()
        for key,value in changes.items():
            if value:parameters[key]=value
            else:parameters.pop(key,None)
        return '?'+parameters.urlencode()
    status_counts=[]
    module_tabs=[]
    if valid:
        all_status={**data,'status':''}
        status_counts=[{'label':'All statuses','count':filtered_rows(checklists,assignments,all_status,client).count(),'url':filter_link(status=''),'active':not data.get('status')}]
        for value,label in form.fields['status'].choices[1:]:
            count=filtered_rows(checklists,assignments,{**data,'status':value},client).count()
            if count or data.get('status')==value:status_counts.append({'label':label,'count':count,'url':filter_link(status=value),'active':data.get('status')==value})
        for value,label in form.fields['module'].choices:
            module_tabs.append({'label':label,'count':filtered_rows(checklists,assignments,{**data,'module':value},client).count(),'url':filter_link(module=value),'active':data.get('module','')==value})
    sort_links={}
    sort_aria={key:'none' for key in ['site','project','module','status','updated']}
    current_sort=data.get('sort') or 'updated'
    if current_sort in {'updated','oldest'}:sort_aria['updated']='descending' if current_sort=='updated' else 'ascending'
    elif current_sort.removesuffix('_desc') in sort_aria:sort_aria[current_sort.removesuffix('_desc')]='descending' if current_sort.endswith('_desc') else 'ascending'
    for column in ['site','project','module','status']:
        next_sort=column+'_desc' if data.get('sort')==column else column
        sort_links[column]=filter_link(sort=next_sort)
    sort_links['updated']=filter_link(sort='oldest' if data.get('sort','updated')=='updated' else 'updated')
    response=render(request,'dashboards/task_explorer.html',{'sort_aria':sort_aria,'active_view':'tasks','selected_project_id':str(data['project'].pk) if data.get('project') else '', 'selected_industry':data.get('industry',''),'status_counts':status_counts,'module_tabs':module_tabs,'sort_links':sort_links,'form':form,'page_obj':page,'filter_query':query.urlencode(),'export_query':export_query.urlencode(),'is_client':client,'total':page.paginator.count})
    response['Cache-Control']='private, no-store'
    return response
