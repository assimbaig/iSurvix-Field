"""Loopback-only first-run account setup without shipped credentials."""
import ipaddress

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters

from .models import PhotoWorkerLease, Profile


@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('password1', 'password2')
def setup(request):
    try:
        local = ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')).is_loopback
    except ValueError:
        local = False
    if not getattr(settings, 'LOCAL_AI_ENABLED', False) or not local:
        raise Http404()
    User = get_user_model()
    if User.objects.filter(is_superuser=True).exists():
        return redirect('/local/')
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # A write lock serializes first-run setup on local SQLite as well.
            PhotoWorkerLease.objects.get_or_create(key='admin_setup', defaults={
                'owner': '', 'expires_at': timezone.now()})
            PhotoWorkerLease.objects.filter(key='admin_setup').update(expires_at=timezone.now())
            if User.objects.filter(is_superuser=True).exists():
                return redirect('/local/')
            user = form.save(commit=False)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = Profile.Roles.SUPER_ADMIN
            profile.save(update_fields=['role'])
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/local/')
    response = render(request, 'dashboards/local_setup.html', {'form': form})
    response['Cache-Control'] = 'no-store'
    return response
