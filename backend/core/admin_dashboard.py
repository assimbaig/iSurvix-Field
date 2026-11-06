"""Read-only company Admin overview, using current project access boundaries.

Counters describe saved records, not evidence links, physical-file verification,
AI compliance or approval. Historical records without a cheaply verifiable stage
remain explicitly unclassified instead of hashing every historical submission.
"""
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Case, CharField, Count, Exists, F, OuterRef, Q, Value, When
from django.db.models.functions import Trim
from django.urls import reverse

from .access import accessible_projects, company_id_for, role_for
from .models import (
    Checklist, ClientOrganization, Company, GovernanceAudit, PhotoEvidence,
    Profile, RevisionDecision, WorkAssignment,
)


COUNT_DEFINITIONS={
    'sites':'Distinct nonempty site IDs within each permitted project. A site can have several activities.',
    'photos':'Unique saved photo evidence IDs, counted once regardless of checklist links or analysis revisions.',
    'activities':'Saved checklist tasks plus assignments that do not yet have a checklist. Linked records count once.',
    'projects':'Projects you can currently access within the selected company/project/industry scope.',
    'clients':'Client organizations in your company and bound industry; a selected project shows only its client.',
    'people':'Distinct active, unlocked project members with an effective grant or permitted legacy primary project.',
}


def dashboard_return_scope(request):
    """Presentation-only return hints. They never confer project authority."""
    if (request.method!='POST' or request.POST.get('return_view')!='dashboard'
            or role_for(request.user)!=Profile.Roles.ADMIN):
        return None
    projects=accessible_projects(request.user)
    chosen=request.POST.get('dashboard_project','')
    selected=None
    if chosen and chosen!='all' and chosen.isascii() and chosen.isdigit() and len(chosen)<=19:
        if int(chosen)<=9223372036854775807:
            selected=projects.filter(pk=int(chosen)).values('pk','industry').first()
    industry=request.POST.get('dashboard_industry','')[:20]
    profile=request.user.profile
    permitted_industry=getattr(profile.admin_industry,'code','')
    if industry and not (industry==permitted_industry or projects.filter(industry=industry).exists()):
        industry=''
    if selected and industry and selected['industry']!=industry:
        industry=selected['industry']
    return {'project':str(selected['pk']) if selected else 'all','industry':industry}


def dashboard_return_url(request,created_project=None):
    scope=dashboard_return_scope(request)
    if scope is None:return None
    query={'view':'dashboard','project':str(created_project.pk) if created_project else scope['project']}
    industry=created_project.industry if created_project else scope['industry']
    if industry:query['industry']=industry
    return reverse('governance_home')+'?'+urlencode(query)


def _query(request):
    query=request.GET.copy()
    returned=dashboard_return_scope(request)
    if returned is not None:
        for key,value in returned.items():query[key]=value
    query['view']='dashboard'
    return query


def _site_rows(checklists,assignments):
    first=checklists.order_by().annotate(site_key=Trim('site_id')).exclude(site_key='').values('project_id','site_key')
    second=assignments.order_by().annotate(site_key=Trim('site_id')).exclude(site_key='').values('project_id','site_key')
    return first.union(second)


def _project_site_counts(checklists,assignments):
    # Django supports COUNT on a UNION but not annotate after union. Compile the
    # same scoped QuerySets and use a parameterized SQL aggregate over their
    # derived table. No caller data, identifiers or raw filter text is appended.
    sql,params=_site_rows(checklists,assignments).query.get_compiler(connection=connection).as_sql()
    column=connection.ops.quote_name('project_id')
    with connection.cursor() as cursor:
        cursor.execute('SELECT '+column+', COUNT(*) FROM ('+sql+') overview_sites GROUP BY '+column,params)
        return dict(cursor.fetchall())


def _staged_checklists(checklists):
    """Use stored route/immutable decisions; no photo or revision JSON reads."""
    decisions=RevisionDecision.objects.filter(revision_id=OuterRef('review_policy__current_revision_id'))
    query=checklists.order_by().annotate(
        _ad_returned=Exists(decisions.filter(action__in=['return','customer_reject'])),
        _ad_approved=Exists(decisions.filter(action='approve')),
        _ad_validated=Exists(decisions.filter(action='validate')),
    )
    independent=Q(governance_mode=Checklist.GovernanceMode.INDEPENDENT,review_policy__current_revision_id__isnull=False)
    closed=(Q(client_review_completed_at__isnull=False)|Q(client_review_required=False)
            |Q(work_assignment__status=WorkAssignment.Status.COMPLETED))
    return query.annotate(_ad_stage=Case(
        When(review_route_record__isnull=False,then=F('review_route_record__stage')),
        When(independent & Q(_ad_returned=True),then=Value('engineer')),
        When(independent & Q(_ad_approved=False,_ad_validated=True,
            review_policy__current_revision__workflow_version=2),then=Value('team_lead')),
        When(independent & Q(_ad_approved=False,_ad_validated=True),then=Value('project_manager')),
        When(independent & Q(_ad_approved=False,review_policy__current_revision__workflow_version=2),then=Value('quality_engineer')),
        When(independent & Q(_ad_approved=False),then=Value('team_lead')),
        When(Q(status=Checklist.Status.FINAL)&closed,then=Value('closed')),
        When(status=Checklist.Status.FINAL,client_review_required=True,then=Value('client')),
        When(status=Checklist.Status.FINAL,then=Value('team_lead')),
        When(status__in=[Checklist.Status.DRAFT,Checklist.Status.REJECTED],then=Value('engineer')),
        default=Value('unknown'),output_field=CharField(),
    ))


def _review_counts(checklists):
    totals={'quality_engineer':0,'team_lead':0,'client':0,'unknown':0}
    by_project={}
    for row in _staged_checklists(checklists).values('project_id','_ad_stage').annotate(total=Count('pk')):
        stage=row['_ad_stage']
        if stage in {'engineer','closed'}:continue
        # A retained v1 Project Manager stage is historical; do not rename it
        # Team Lead or accidentally assign Admin an approval power.
        key=stage if stage in totals else 'unknown'
        totals[key]+=row['total']
        by_project[row['project_id']]=by_project.get(row['project_id'],0)+row['total']
    return totals,by_project


def _task_url(project=None,industry='',site=''):
    query={}
    if project:query['project']=project
    if industry:query['industry']=industry
    if site:query['q']=site
    return reverse('task_explorer')+('?' + urlencode(query) if query else '')


def build_admin_dashboard(request,projects):
    """Build a bounded metadata overview. The supplied scope can only narrow."""
    actor=request.user
    if role_for(actor)!=Profile.Roles.ADMIN:
        raise PermissionDenied('Company overview requires a scoped company Admin.')
    projects=projects.filter(pk__in=accessible_projects(actor).values('pk')).order_by()
    company_id=company_id_for(actor)
    company_name=Company.objects.filter(pk=company_id).values_list('name',flat=True).first()
    profile=actor.profile
    industry_id=profile.admin_industry_id
    checklists=Checklist.objects.filter(project__in=projects)
    assignments=WorkAssignment.objects.filter(project__in=projects,checklist__isnull=True)
    photos=PhotoEvidence.objects.filter(checklist__project__in=projects)
    clients=ClientOrganization.objects.filter(company_id=company_id,industry_id=industry_id)
    query=_query(request)
    selected=query.get('project','')
    if selected and selected!='all':
        clients=clients.filter(projects__in=projects).distinct()
    from .governance_views import workspace_members
    members=workspace_members(actor,projects,False).filter(
        is_active=True,is_superuser=False,profile__is_locked=False)
    people_by_role=[{'role':row['profile__role'],
        'label':dict(Profile.Roles.choices).get(row['profile__role'],'Other retained role'),'count':row['total']}
        for row in members.order_by().values('profile__role').annotate(total=Count('pk',distinct=True)).order_by('profile__role')]
    summary={'sites':_site_rows(checklists,assignments).count(),'photos':photos.count(),
        'activities':checklists.count()+assignments.count(),'projects':projects.count(),
        'clients':clients.count(),'people':sum(row['count'] for row in people_by_role)}
    review_counts,project_reviews=_review_counts(checklists)
    search=query.get('admin_project_q','').strip()[:200]
    visible=projects
    if search:
        visible=visible.filter(Q(name__icontains=search)|Q(client_organization__name__icontains=search,
            client_organization__company_id=F('company_id'),client_organization__industry__code=F('industry')))
    records=visible.order_by('name','pk').values('pk','name','company_id','industry','client_organization_id',
        'client_organization__name','client_organization__company_id','client_organization__industry__code')
    page=Paginator(records,25).get_page(query.get('admin_projects_page'))
    rows=list(page.object_list)
    page_ids=[row['pk'] for row in rows]
    page_checklists=checklists.filter(project_id__in=page_ids)
    page_assignments=assignments.filter(project_id__in=page_ids)
    checklist_counts=dict(page_checklists.order_by().values('project_id').annotate(total=Count('pk')).values_list('project_id','total'))
    assignment_counts=dict(page_assignments.order_by().values('project_id').annotate(total=Count('pk')).values_list('project_id','total'))
    photo_counts=dict(photos.filter(checklist__project_id__in=page_ids).order_by().values('checklist__project_id').annotate(total=Count('pk')).values_list('checklist__project_id','total'))
    site_counts=_project_site_counts(page_checklists,page_assignments) if page_ids else {}
    project_rows=[]
    for row in rows:
        pk=row['pk']
        valid_client=(row['client_organization__company_id']==row['company_id']
            and row['client_organization__industry__code']==row['industry'])
        project_rows.append({'id':pk,'name':row['name'],
            'client_name':row['client_organization__name'] if valid_client else '',
            'site_count':site_counts.get(pk,0),
            'activity_count':checklist_counts.get(pk,0)+assignment_counts.get(pk,0),
            'photo_count':photo_counts.get(pk,0),'review_count':project_reviews.get(pk,0),
            'url':reverse('governance_home')+'?'+urlencode({'view':'projects','project':pk})})
    def page_url(number):
        values=query.copy();values['admin_projects_page']=str(number)
        return reverse('governance_home')+'?'+values.urlencode()
    recent=[]
    events=GovernanceAudit.objects.filter(project__in=projects).order_by('-created_at','-pk').annotate(
        site_value=F('details__site_id')).values('pk','action','actor_name','created_at','project_id','project__name','site_value')[:8]
    for event in events:
        site=event['site_value']
        if not isinstance(site,str) or len(site)>120 or any(ord(char)<32 for char in site):site=''
        recent.append({'id':event['pk'],'site_id':site,'project_name':event['project__name'],
            'actor_name':event['actor_name'],'action':event['action'].replace('_',' ').capitalize(),
            'at':event['created_at'],'url':_task_url(event['project_id'],site=site)})
    selected_project=projects.filter(pk=selected).values_list('name',flat=True).first() if selected and selected!='all' and selected.isascii() and selected.isdigit() else None
    return {'company_name':company_name or 'Company not configured','scope_label':selected_project or 'All permitted company projects',
        'summary':summary,'count_definitions':COUNT_DEFINITIONS,'projects':project_rows,
        'projects_pagination':{'page':page,'label':'Company project pages',
            'previous_url':page_url(page.previous_page_number()) if page.has_previous() else '',
            'next_url':page_url(page.next_page_number()) if page.has_next() else ''},
        'review_counts':review_counts,'recent_activity':recent,'people_by_role':people_by_role,
        'search':search,'search_filters':[(key,value) for key,value in query.items() if key not in {'admin_project_q','admin_projects_page'}],
        'tasks_url':_task_url(selected_project and selected,query.get('industry',''))}
