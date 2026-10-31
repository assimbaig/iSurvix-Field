"""Compact administrative AI settings; no inference or credential exchange here."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from .access import company_id_for, is_super_admin, role_for
from .ai_settings_forms import AISettingsForm, provider_aliases
from .governance_views import guarded_write
from .models import Company, Profile


def _guard(actor, company_id=None):
    if is_super_admin(actor):
        return
    profile = Profile.objects.select_related('admin_industry').filter(user_id=actor.pk).first()
    if (role_for(actor) != Profile.Roles.ADMIN or not profile or
            profile.admin_industry_pending or not profile.admin_industry_id or
            not profile.admin_industry.is_active or not company_id_for(actor) or
            (company_id is not None and company_id_for(actor) != company_id)):
        raise PermissionDenied('AI settings require current administration access within your company.')


@login_required
@never_cache
@require_GET
def index(request):
    _guard(request.user)
    if not is_super_admin(request.user):
        return redirect('ai_settings_company', company_id=company_id_for(request.user))
    return render(request, 'dashboards/ai_settings.html', {
        'active_view': 'ai_settings', 'companies': Company.objects.order_by('name', 'pk'),
        'is_super_admin': True,
    })


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
@guarded_write
def company_settings(request, company_id):
    _guard(request.user, company_id)
    company = get_object_or_404(Company, pk=company_id)
    from .ai_processing_models import AIProcessingSettings
    from .ai_processing_service import update_settings
    config = AIProcessingSettings.objects.filter(company_id=company_id).first()
    defaults = {
        'version': 0, 'enabled': False, 'primary_provider': 'local',
        'local_model': 'qwen3.5:4b', 'api_model': '', 'api_endpoint': '',
        'allow_external_evidence': False, 'fallback_enabled': False,
        'daily_request_limit': 2000, 'request_timeout': 120,
    }
    initial = {key: getattr(config, key) for key in defaults} if config else defaults
    status = 200
    form = AISettingsForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST':
        if set(request.POST) - set(form.fields) - {'csrfmiddlewaretoken'}:
            return HttpResponse('Only the displayed configuration fields are accepted. Credentials are managed privately by the server operator.', status=400)
        status = 400
        if form.is_valid():
            data = dict(form.cleaned_data)
            version = data.pop('version')
            try:
                update_settings(request.user, company, data, expected_version=version)
            except ValidationError as error:
                errors = getattr(error, 'error_list', [])
                conflict = any(getattr(item, 'code', None) == 'conflict' for item in errors)
                if conflict:
                    status = 409
                    form.add_error(None, 'Settings changed since this page opened. Your input remains below. Reload the saved settings before applying it again.')
                else:
                    # Service errors describe configuration policy only; no raw provider response is rendered.
                    form.add_error(None, error)
            else:
                messages.success(request, 'AI settings saved. Existing evidence, results and human decisions are unchanged.')
                return redirect('ai_settings_company', company_id=company_id)
    return render(request, 'dashboards/ai_settings.html', {
        'active_view': 'ai_settings', 'company': company, 'form': form,
        'configuration': config, 'available_provider_count': len(provider_aliases()),
        'is_super_admin': is_super_admin(request.user),
    }, status=status)
