"""Read-only platform desk, backed by paginated administrative records."""
from collections import defaultdict
from urllib.parse import urlencode
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .access import is_super_admin
from .models import Company, CompanyApplication, GovernanceAudit, Profile, Project, WorkAssignment, SubmissionRevision, IndustryCatalog


def _identifier(request, name):
    value=request.GET.get(name,'')
    if not value:return None
    if not value.isascii() or not value.isdigit() or len(value)>19:
        raise Http404()
    result=int(value)
    if not 0<result<=9223372036854775807:raise Http404()
    return result


def _url(request, **scope):
    query={'view':'companies'}
    for key in ('q','desk_page','desk_records','app_status'):
        if request.GET.get(key):query[key]=request.GET[key][:200]
    query.update({key:value for key,value in scope.items() if value is not None})
    return reverse('governance_home')+'?'+urlencode(query)


def invitation_state(invitation):
    if invitation is None:return 'Not issued'
    if invitation.accepted_at:return 'Accepted'
    if invitation.revoked_at:return 'Revoked'
    if invitation.expires_at<=timezone.now():return 'Expired'
    return 'Issued · acceptance pending'


def _page(request, records, parameter='hierarchy_page'):
    return Paginator(records,25).get_page(request.GET.get(parameter))


def _navigation(request, page, parameter):
    def url(number):
        query=request.GET.copy()
        query['view']='companies'
        query[parameter]=number
        return reverse('governance_home')+'?'+query.urlencode()
    return {'page':page,'label':'Saved record pages',
            'previous_url':url(page.previous_page_number()) if page.has_previous() else '',
            'next_url':url(page.next_page_number()) if page.has_next() else ''}


def build_superadmin_desk(request):
    if not is_super_admin(request.user):raise PermissionDenied('Platform administration is required.')
    search=request.GET.get('q','').strip()[:200]
    companies=Company.objects.order_by('name','pk')
    if search:companies=companies.filter(Q(name__icontains=search)|Q(profiles__role=Profile.Roles.ADMIN,profiles__user__email__icontains=search)).distinct()
    company_page=_page(request,companies,'desk_page')
    visible=list(company_page.object_list)
    ids=[company.pk for company in visible]
    def counts(queryset, field):
        return {row[field]:row['n'] for row in queryset.values(field).annotate(n=Count('pk'))}
    project_counts=counts(Project.objects.filter(company_id__in=ids),'company_id')
    site_counts=counts(WorkAssignment.objects.filter(project__company_id__in=ids),'project__company_id')
    resolved=Profile.objects.annotate(resolved_company=Coalesce('company_id','project__company_id'))
    user_counts=counts(resolved.filter(resolved_company__in=ids),'resolved_company')
    admins=defaultdict(list); industries=defaultdict(set)
    for profile in resolved.filter(resolved_company__in=ids,role=Profile.Roles.ADMIN).select_related('user','admin_industry'):
        admins[profile.resolved_company].append(profile.user.get_full_name() or profile.user.username)
        if profile.admin_industry_id:industries[profile.resolved_company].add(profile.admin_industry.name)
    industry_names=dict(IndustryCatalog.objects.values_list('code','name'))
    for project_industry in Project.objects.filter(company_id__in=ids).values('company_id','industry').distinct():
        industries[project_industry['company_id']].add(industry_names.get(project_industry['industry'],project_industry['industry']))
    applications={app.company_id:app for app in CompanyApplication.objects.filter(company_id__in=ids).select_related('industry','invitation','invitation__email_delivery')}
    rows=[]
    for company in visible:
        app=applications.get(company.pk)
        if app:industries[company.pk].add(app.industry.name)
        rows.append({'company':company,'url':_url(request,desk_company=company.pk),
            'admin_label':', '.join(admins[company.pk]) or 'Not assigned',
            'industry_label':', '.join(sorted(industries[company.pk])) or 'Not recorded',
            'project_count':project_counts.get(company.pk,0),'site_count':site_counts.get(company.pk,0),
            'user_count':user_counts.get(company.pk,0),'application':app,
            'onboarding_status':app.get_status_display() if app else 'Existing company',
            'invite_status':invitation_state(app.invitation if app else None)})
    company_page.object_list=rows
    applications=CompanyApplication.objects.select_related('industry','company','invitation','invitation__email_delivery').order_by('-created_at','-pk')
    if search:applications=applications.filter(Q(name__icontains=search)|Q(email__icontains=search))
    app_status=request.GET.get('app_status','')
    if app_status and app_status not in CompanyApplication.Status.values:raise Http404()
    if app_status:applications=applications.filter(status=app_status)
    application_page=_page(request,applications,'desk_page')
    application_rows=[]
    for application in application_page:
        application_rows.append({'application':application,'url':reverse('company_onboarding_detail',args=[application.pk]),
            'invite_status':invitation_state(application.invitation),
            'email_status':application.invitation.email_delivery_label if application.invitation_id else 'No invitation'})
    application_page.object_list=application_rows
    selected={key:_identifier(request,'desk_'+key) for key in ('company','project','site','submission')}
    if (selected['project'] and not selected['company'] or selected['site'] and not selected['project'] or selected['submission'] and not selected['site']):raise Http404()
    company=get_object_or_404(Company,pk=selected['company']) if selected['company'] else None
    project=get_object_or_404(Project,pk=selected['project'],company=company) if selected['project'] else None
    site=get_object_or_404(WorkAssignment.objects.select_related('checklist','assigned_to').defer('checklist__answer_data','checklist__remark_data','checklist__image_data','checklist__schema_snapshot','checklist__branding_snapshot','checklist__review_history','checklist__section_approvals','checklist__quality_approval','checklist__client_approval'),pk=selected['site'],project=project) if selected['site'] else None
    revision=get_object_or_404(SubmissionRevision.objects.defer('snapshot').select_related('submitted_by'),pk=selected['submission'],checklist_id=site.checklist_id) if selected['submission'] else None
    scope={};breadcrumbs=[{'label':'Companies','url':_url(request)}]
    for key,record,label in [('company',company,getattr(company,'name','')),('project',project,getattr(project,'name','')),('site',site,getattr(site,'site_id','')),('submission',revision,'Revision '+str(revision.number) if revision else '')]:
        if record:
            scope['desk_'+key]=record.pk
            breadcrumbs.append({'label':label,'url':_url(request,**scope)})
    project_page=_page(request,Project.objects.filter(company=company).select_related('administrator').order_by('name','pk') if company and not project else [])
    project_page.object_list=[{'project':row,'url':_url(request,desk_company=company.pk,desk_project=row.pk)} for row in project_page]
    site_page=_page(request,WorkAssignment.objects.filter(project=project).select_related('assigned_to').order_by('site_id','pk') if project and not site else [])
    site_page.object_list=[{'site':row,'url':_url(request,desk_company=company.pk,desk_project=project.pk,desk_site=row.pk)} for row in site_page]
    revision_page=_page(request,SubmissionRevision.objects.filter(checklist_id=site.checklist_id).defer('snapshot').select_related('submitted_by').order_by('-number','-pk') if site and site.checklist_id else [])
    revision_page.object_list=[{'submission':row,'url':_url(request,desk_company=company.pk,desk_project=project.pk,desk_site=site.pk,desk_submission=row.pk)} for row in revision_page]
    return {'counts':{'companies':Company.objects.count(),'users':User.objects.count(),'projects':Project.objects.count(),'sites':WorkAssignment.objects.count()},
        'company_rows':company_page,'applications':application_page,'application_rows':application_page,'app_status':app_status,'application_statuses':CompanyApplication.Status.choices,'records':request.GET.get('desk_records','companies'),'search':search,'selected_company':company,'selected_project':project,'selected_site':site,'selected_submission':revision,
        'projects':project_page,'sites':site_page,'submissions':revision_page,'breadcrumbs':breadcrumbs,
        'company_navigation':_navigation(request,company_page,'desk_page'),'application_navigation':_navigation(request,application_page,'desk_page'),
        'hierarchy_navigation':_navigation(request,revision_page if site else site_page if project else project_page,'hierarchy_page'),
        'legacy_checklist':site.checklist if site and site.checklist_id and not revision_page.paginator.count else None,
        'submission_history':list(revision.decisions.select_related('actor').order_by('created_at','pk')[:25]) if revision else [],
        'pending_total':CompanyApplication.objects.filter(status__in=['applied','reviewed','provisioned']).count(),
        'pending':CompanyApplication.objects.filter(status__in=['applied','reviewed','provisioned']).select_related('industry','invitation','company').order_by('created_at','pk')[:12],
        'recent_audit':GovernanceAudit.objects.select_related('actor','project').order_by('-created_at','-pk')[:12]}
