"""Single-use registered-email recovery via the existing supervised email worker."""
from datetime import timedelta
import hashlib
import hmac
import ipaddress
import re
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.debug import sensitive_variables

from .account_recovery_models import AccountRecoveryRequest,AccountRecoveryThrottle
from .invitation_email import _public_origin
from .notification_email import GraphMailClient,NotificationEmailError

WINDOW=timedelta(hours=1)
EXPIRY=timedelta(minutes=30)
MAX_ATTEMPTS=3
LEASE_SECONDS=120
GENERIC_MESSAGE='If this address belongs to an eligible account, a password reset link will be queued. Check your email, including spam. If it does not arrive, contact your administrator.'


def _fingerprint(purpose,value,key=None):
    return salted_hmac('core.account-recovery.'+purpose,str(value),
        secret=settings.SECRET_KEY if key is None else key,algorithm='sha256').hexdigest()


def _reset_token(row,key=None):
    return _fingerprint('token.v1',row.pk,key)


def _email_key(email):
    return _fingerprint('email.v1',email.strip().casefold())


def _auth_key(user):
    return _fingerprint('auth.v1',f'{user.pk}|{user.password}|{user.email.casefold()}|{user.last_login}')


def _audit(row,action,code=''):
    from .models import GovernanceAudit
    GovernanceAudit.objects.create(action='account_recovery.'+action,actor_name='',
        details={'request_id':str(row.pk),'user_id':row.user_id,'status':row.status,'code':code})


def _lock(now):
    # Write first: serializes SQLite and row-locking databases without trusting
    # process-local cache limits. Public requests cannot create arbitrary keys
    # after the shared global budget is exhausted.
    AccountRecoveryThrottle.objects.get_or_create(key='global',defaults={'window_started_at':now})
    AccountRecoveryThrottle.objects.filter(key='global').update(hits=F('hits'))


def _take(key,limit,now):
    row,_=AccountRecoveryThrottle.objects.get_or_create(key=key,defaults={'window_started_at':now})
    if row.window_started_at<=now-WINDOW:
        row.window_started_at=now;row.hits=0
    if row.hits>=limit:return False
    row.hits+=1
    row.save(update_fields=['hits','window_started_at'])
    return True


def _eligible_user(user):
    return bool(user and user.is_active and user.has_usable_password()
        and not getattr(getattr(user,'profile',None),'is_locked',True))


@sensitive_variables('email')
def request_reset(email,ip):
    """Always return None. Unknown, blocked and rate-limited accounts look alike."""
    if not isinstance(email,str) or len(email)>254:return None
    email=email.strip()
    try:validate_email(email)
    except ValidationError:return None
    try:ip=str(ipaddress.ip_address(ip))
    except (ValueError,TypeError):ip='unknown'
    now=timezone.now()
    with transaction.atomic():
        _lock(now)
        AccountRecoveryThrottle.objects.exclude(key='global').filter(window_started_at__lte=now-WINDOW).delete()
        local_limits={'ip:'+_fingerprint('ip.v1',ip):10,'account:'+_email_key(email):3}
        # Check existing local windows before debiting shared capacity. A denied
        # IP/account must not prevent unrelated users from requesting recovery.
        # This read allocates no keys: moving _take(local) ahead of global would
        # let rotating identifiers create unbounded rows after global exhaustion.
        # The existing global write lock serializes these checks and reservations.
        current=AccountRecoveryThrottle.objects.filter(key__in=local_limits,window_started_at__gt=now-WINDOW)
        if any(row.hits>=local_limits[row.key] for row in current):return None
        if not _take('global',100,now):return None
        for key,limit in local_limits.items():
            if not _take(key,limit,now):return None
        # Locally admitted unknown/blocked addresses still count, preserving the
        # generic response and at most201 allocated keys per global window.
        users=list(get_user_model().objects.select_related('profile').filter(email__iexact=email)[:2])
        if len(users)!=1 or not _eligible_user(users[0]):return None
        if not getattr(settings,'NOTIFICATION_EMAIL_ENABLED',False):return None
        user=users[0]
        # New request invalidates earlier unconsumed links, without deleting
        # history or repeating a previously accepted/ambiguous transport POST.
        AccountRecoveryRequest.objects.filter(user=user,used_at__isnull=True,invalidated_at__isnull=True).update(invalidated_at=now)
        row=AccountRecoveryRequest(id=uuid.uuid4(),user=user,email_fingerprint=_email_key(user.email),
            auth_fingerprint=_auth_key(user),expires_at=now+EXPIRY)
        row.token_fingerprint=hashlib.sha256(_reset_token(row).encode()).hexdigest()
        row.save();_audit(row,'queued')
    return None


def _current(row):
    user=row.user
    return bool(row.used_at is None and row.invalidated_at is None and row.expires_at>timezone.now()
        and _eligible_user(user) and hmac.compare_digest(row.email_fingerprint,_email_key(user.email))
        and hmac.compare_digest(row.auth_fingerprint,_auth_key(user)))


@sensitive_variables('token')
def valid_reset(request_id,token):
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):return None
    try:row=AccountRecoveryRequest.objects.select_related('user','user__profile').filter(pk=request_id).first()
    except (ValidationError,ValueError,TypeError):return None
    if not row or not _current(row):return None
    if not hmac.compare_digest(row.token_fingerprint,hashlib.sha256(token.encode()).hexdigest()):return None
    return row


class ResetUnavailable(Exception):
    pass


def recover_interrupted_reset_emails():
    now=timezone.now()
    with transaction.atomic():
        _lock(now)
        rows=list(AccountRecoveryRequest.objects.filter(status='sending',lease_expires_at__lte=now))
        for row in rows:
            row.status='uncertain';row.error_code='worker_interrupted';row.lease_id=None;row.lease_expires_at=None
            row.save(update_fields=['status','error_code','lease_id','lease_expires_at','updated_at']);_audit(row,'uncertain','worker_interrupted')
    return len(rows)


def retry_failed_reset_emails():
    now=timezone.now();count=0
    with transaction.atomic():
        _lock(now)
        for row in AccountRecoveryRequest.objects.select_related('user','user__profile').filter(status='failed',expires_at__gt=now):
            if not _current(row):continue
            row.status='queued';row.error_code='';row.attempts=0;row.available_at=now
            row.save(update_fields=['status','error_code','attempts','available_at','updated_at']);_audit(row,'retry');count+=1
    return count


def _finish(row,status,code=''):
    with transaction.atomic():
        current=AccountRecoveryRequest.objects.select_for_update().filter(pk=row.pk,status='sending',lease_id=row.lease_id).first()
        if current is None:return
        current.status=status;current.error_code=code;current.lease_id=None;current.lease_expires_at=None
        if status=='accepted':current.accepted_at=timezone.now()
        if status=='queued':current.available_at=timezone.now()+timedelta(seconds=30*current.attempts)
        current.save(update_fields=['status','error_code','lease_id','lease_expires_at','accepted_at','available_at','updated_at'])
        _audit(current,status,code)


def _message(row):
    current=AccountRecoveryRequest.objects.select_related('user','user__profile').get(pk=row.pk)
    if not _current(current):raise ResetUnavailable()
    token=next((value for key in [settings.SECRET_KEY,*settings.SECRET_KEY_FALLBACKS]
        if hmac.compare_digest(current.token_fingerprint,hashlib.sha256((value:=_reset_token(current,key)).encode()).hexdigest())),None)
    if token is None:raise ResetUnavailable()
    link=_public_origin()+reverse('account_password_reset_confirm',args=[current.pk,token])
    name=current.user.get_full_name().strip() or current.user.username
    body=(f'Hello {name},\n\nA password reset was requested for your iField account.\n'
        f'Choose a new password using this private, single-use link:\n{link}\n\n'
        f'This link expires at {current.expires_at:%Y-%m-%d %H:%M UTC}. '
        'Requesting another link or changing your account invalidates it.\n'
        'If you did not request this, ignore the email. Your existing password has not changed. '
        'Never send your password by email.')
    return current.user.email,'Reset your iField password',body


def process_next_reset_email():
    if not getattr(settings,'NOTIFICATION_EMAIL_ENABLED',False):return False
    recover_interrupted_reset_emails()
    with transaction.atomic():
        now=timezone.now();_lock(now)
        row=AccountRecoveryRequest.objects.filter(status='queued',available_at__lte=now,attempts__lt=MAX_ATTEMPTS).first()
        if row is None:return False
        row.status='sending';row.attempts+=1;row.lease_id=uuid.uuid4();row.lease_expires_at=now+timedelta(seconds=LEASE_SECONDS)
        row.save(update_fields=['status','attempts','lease_id','lease_expires_at','updated_at']);_audit(row,'started')
    try:
        recipient,subject,body=_message(row)
        GraphMailClient().send(recipient,subject,body,before_send=lambda:_message(row),branded=True)
    except ResetUnavailable:_finish(row,'cancelled','account_unavailable')
    except NotificationEmailError as error:
        state='uncertain' if error.uncertain else 'queued' if error.retryable and row.attempts<MAX_ATTEMPTS else 'failed'
        _finish(row,state,error.code)
    except Exception:_finish(row,'uncertain','unexpected_delivery_failure')
    else:_finish(row,'accepted')
    return True
