"""Public CSRF-protected recovery; token consumption never signs a user in."""
from django.db import transaction,OperationalError,IntegrityError
from django.http import HttpResponse
from django.shortcuts import render,redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods,require_GET
from .account_recovery import request_reset,valid_reset,_lock,_audit,GENERIC_MESSAGE
from .account_recovery_forms import RecoveryRequestForm,RecoveryPasswordForm
from .account_recovery_models import AccountRecoveryRequest
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
import ipaddress


def _response(request,template,context=None,status=200):
    response=render(request,template,context or {},status=status)
    response['Referrer-Policy']='same-origin'
    response['Cache-Control']='no-store'
    return response


@never_cache
@require_http_methods(['GET','POST'])
def request_password_reset(request):
    form=RecoveryRequestForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        ip=request.META.get('REMOTE_ADDR','unknown')
        if getattr(settings,'ACCOUNT_RECOVERY_TRUST_PROXY_IP',False):
            # Enabled only in the private-backend deployment whose Nginx
            # overwrites this header. Never trust caller-supplied XFF chains.
            try:ip=str(ipaddress.ip_address(request.META.get('HTTP_X_REAL_IP','')))
            except (ValueError,TypeError):pass
        try:request_reset(form.cleaned_data['email'],ip)
        except (OperationalError,IntegrityError):
            # No account/delivery state leaks through a different busy response.
            pass
        return redirect('account_password_reset_done')
    return _response(request,'account_recovery/request.html',{'form':form},400 if request.method=='POST' else 200)


@never_cache
@require_GET
def reset_done(request):
    return _response(request,'account_recovery/done.html',{'notice':GENERIC_MESSAGE})


@never_cache
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('new_password1','new_password2')
def confirm_password_reset(request,request_id,token):
    row=valid_reset(request_id,token)
    if row is None:return _response(request,'account_recovery/invalid.html',status=400)
    form=RecoveryPasswordForm(row.user,request.POST if request.method=='POST' else None)
    if request.method=='POST':
        try:
            with transaction.atomic():
                _lock(timezone.now())
                row=valid_reset(request_id,token)
                if row is None:return _response(request,'account_recovery/invalid.html',status=400)
                # Serialize against account/password and deliberate profile-lock
                # writes on row-locking backends; SQLite is already write-locked.
                get_user_model().objects.select_for_update().get(pk=row.user_id)
                from .models import Profile
                list(Profile.objects.select_for_update().filter(user_id=row.user_id))
                row=valid_reset(request_id,token)
                if row is None:return _response(request,'account_recovery/invalid.html',status=400)
                form=RecoveryPasswordForm(row.user,request.POST)
                if form.is_valid():
                    now=timezone.now()
                    changed=AccountRecoveryRequest.objects.filter(pk=row.pk,used_at__isnull=True,invalidated_at__isnull=True,expires_at__gt=now).update(used_at=now)
                    if not changed:return _response(request,'account_recovery/invalid.html',status=400)
                    changed_user=form.save(commit=False)
                    changed_user.save(update_fields=['password'])
                    AccountRecoveryRequest.objects.filter(user=row.user,used_at__isnull=True,invalidated_at__isnull=True).update(invalidated_at=now)
                    row.used_at=now;_audit(row,'completed')
                    return redirect('account_password_reset_complete')
        except (OperationalError,IntegrityError):
            form.add_error(None,'The service is busy. Your password was not changed. Retry this form.')
            return _response(request,'account_recovery/confirm.html',{'form':form},503)
    return _response(request,'account_recovery/confirm.html',{'form':form},400 if request.method=='POST' else 200)


@never_cache
@require_GET
def reset_complete(request):
    return _response(request,'account_recovery/complete.html')
