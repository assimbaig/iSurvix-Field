"""Company-scoped customization, no mail send or secret handling in requests."""
from datetime import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404,HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET,require_http_methods
from .access import company_id_for,is_super_admin
from .models import Company,CompanyNotificationSettings
from .custom_notifications import guard,save_settings,KINDS,TOKENS
from .custom_notification_forms import NotificationSettingsForm
from .governance_views import guarded_write

@login_required
@never_cache
@require_GET
def index(request):
    guard(request.user)
    if not is_super_admin(request.user):return redirect('notification_settings_company',company_id=company_id_for(request.user))
    companies=Company.objects.order_by('name','pk')
    search=request.GET.get('q','').strip()[:160]
    if search:companies=companies.filter(name__icontains=search)
    return render(request,'dashboards/notification_settings.html',{'active_view':'notification_settings','companies':Paginator(companies,25).get_page(request.GET.get('page')),'search':search,'is_super_admin':True})

@login_required
@never_cache
@require_http_methods(['GET','POST'])
@guarded_write
def company(request,company_id):
    if not company_id.isascii() or not company_id.isdigit() or len(company_id)>19 or not 0<int(company_id)<=9223372036854775807:raise Http404()
    guard(request.user)
    if not is_super_admin(request.user) and company_id_for(request.user)!=int(company_id):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('This company is outside your administration scope.')
    record=get_object_or_404(Company,pk=int(company_id))
    guard(request.user,record)
    config=CompanyNotificationSettings.objects.filter(company=record).first()
    kind=request.GET.get('kind','submission')
    if kind not in KINDS:raise Http404()
    pair=config.templates.get(kind) if config and isinstance(config.templates,dict) else None
    initial={'version':config.version if config else 0,'kind':kind,'use_default':not bool(pair),
        'subject':pair['subject'] if pair else '', 'body':pair['body'] if pair else '',
        'combined_daily_enabled':config.combined_daily_enabled if config else False,
        'daily_time':config.daily_time if config else time(18),'timezone_name':config.timezone_name if config else 'Asia/Riyadh'}
    form=NotificationSettingsForm(request.POST if request.method=='POST' else None,initial=initial)
    status=200
    if request.method=='POST':
        if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:return HttpResponse('Only displayed notification settings may be saved.',status=400)
        status=400
        if form.is_valid():
            data=form.cleaned_data
            templates=dict(config.templates) if config and isinstance(config.templates,dict) else {}
            if data['use_default']:templates.pop(data['kind'],None)
            else:templates[data['kind']]={'subject':data['subject'],'body':data['body']}
            try:save_settings(request.user,record,expected_version=data['version'],templates=templates,
                combined_daily_enabled=data['combined_daily_enabled'],daily_time=data['daily_time'],timezone_name=data['timezone_name'])
            except ValidationError as error:
                status=409 if getattr(error,'code',None)=='conflict' else 400
                form.add_error(None,error)
            else:
                messages.success(request,'Notification settings saved. No email was sent by this settings request.')
                from django.urls import reverse
                return redirect(reverse('notification_settings_company',args=[record.pk])+'?kind='+data['kind'])
    return render(request,'dashboards/notification_settings.html',{'active_view':'notification_settings','company':record,'form':form,'configuration':config,'kinds':KINDS.items(),'tokens':sorted(TOKENS),'is_super_admin':is_super_admin(request.user)},status=status)
