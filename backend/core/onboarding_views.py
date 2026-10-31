"""Owner-only received applications; no public registration endpoint."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .access import is_super_admin
from .governance_views import guarded_write
from .models import CompanyApplication
from .onboarding_forms import CompanyApplicationActionForm, CompanyApplicationForm
from .onboarding_service import apply_application, invite_application, provision_application, review_application


def _owner(request):
    if not is_super_admin(request.user):
        raise PermissionDenied('Only the platform owner can manage company onboarding.')


def _context(**kwargs):
    return {'active_view': 'administration', **kwargs}


@login_required
@never_cache
@require_GET
def index(request):
    _owner(request)
    applications = CompanyApplication.objects.select_related('industry', 'company', 'invitation')
    page = Paginator(applications, 30).get_page(request.GET.get('page'))
    return render(request, 'onboarding/index.html', _context(page=page))


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@guarded_write
def apply(request):
    _owner(request)
    if request.method == 'POST' and set(request.POST) - {'csrfmiddlewaretoken', 'request_key', 'name', 'email', 'industry'}:
        return HttpResponse('Application intake cannot set account or company authority.', status=400)
    form = CompanyApplicationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            application = apply_application(request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Application recorded. Review it before provisioning a company.')
            return redirect('company_onboarding_detail', application_id=application.pk)
    return render(request, 'onboarding/apply.html', _context(form=form), status=400 if request.method == 'POST' else 200)


@login_required
@never_cache
@require_GET
def detail(request, application_id):
    _owner(request)
    application = get_object_or_404(CompanyApplication.objects.select_related('industry', 'company', 'invitation', 'reviewed_by'), pk=application_id)
    return render(request, 'onboarding/detail.html', _context(application=application))


@login_required
@never_cache
@require_POST
@guarded_write
def action(request, application_id):
    _owner(request)
    application = get_object_or_404(CompanyApplication, pk=application_id)
    if set(request.POST) - {'csrfmiddlewaretoken', 'action', 'review_note'}:
        return HttpResponse('Onboarding authority comes from the saved application.', status=400)
    form = CompanyApplicationActionForm(request.POST)
    token = None
    if form.is_valid():
        try:
            command = form.cleaned_data['action']
            if command in {'approve', 'reject'}:
                application = review_application(request.user, application.pk, approve=command == 'approve', reason=form.cleaned_data['review_note'])
            elif command == 'provision':
                application = provision_application(request.user, application.pk)
            else:
                application, token = invite_application(request.user, application.pk)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if token:
                invite_url = request.build_absolute_uri(reverse('governance_accept_invite', args=[token]))
                return render(request, 'onboarding/detail.html', _context(application=application, invite_url=invite_url))
            messages.success(request, 'Saved application status: ' + application.get_status_display() + '.')
            return redirect('company_onboarding_detail', application_id=application.pk)
    return render(request, 'onboarding/detail.html', _context(application=application, action_form=form), status=400)
