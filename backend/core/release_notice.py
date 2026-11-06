"""Optional all-role update notices; no jobs, inference or engineering writes."""
import json
import logging
import re
import secrets

from django.contrib.auth.decorators import login_required
from django.db import DatabaseError,transaction
from django.http import JsonResponse
from django.urls import NoReverseMatch,reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .access import role_for
from .operations_service import release_id
from .release_note_content import LOCAL_RELEASE_KEY,NOTES
from .release_notice_models import ReleaseNoticeAcknowledgement,SESSION_KEY


logger=logging.getLogger(__name__)
TOKEN=re.compile(r'[A-Za-z0-9_-]{16,80}\Z')
RELEASE=re.compile(r'(?:[0-9a-f]{40}|local-[a-z0-9-]{1,74})\Z')


def current_release_key():
    installed=release_id()
    return installed if installed!='unknown' else LOCAL_RELEASE_KEY


def _eligible(request):
    user=getattr(request,'user',None)
    return bool(user is not None and user.is_authenticated and role_for(user) is not None)


def _slot(request,key,create=False):
    if not hasattr(request,'session'):return None
    value=request.session.get(SESSION_KEY)
    if (isinstance(value,dict) and type(value.get('user_id')) is int
            and value['user_id']==request.user.pk and value.get('release_key')==key
            and isinstance(value.get('nonce'),str) and TOKEN.fullmatch(value['nonce'])
            and isinstance(value.get('actor_key'),str) and TOKEN.fullmatch(value['actor_key'])
            and type(value.get('dismissed')) is bool and type(value.get('remembered')) is bool):
        return value
    if not create:return None
    value={'user_id':request.user.pk,'release_key':key,'nonce':secrets.token_urlsafe(24),
        'actor_key':secrets.token_urlsafe(18),'dismissed':False,'remembered':False}
    request.session[SESSION_KEY]=value
    return value


def release_notice_context(request):
    """A failed optional preference read must not take down the review page."""
    user=getattr(request,'user',None)
    if user is None or not user.is_authenticated:return {'release_notice':None}
    try:
        ack_url=reverse('release_notice_acknowledge')
    except NoReverseMatch:
        # Django admin or an embedded URLConf can intentionally omit the Field
        # acknowledgement route. Do not query preferences or seed session state.
        return {'release_notice':None}
    try:
        if not _eligible(request):return {'release_notice':None}
    except DatabaseError:
        logger.warning('release_notice.account_unavailable')
        return {'release_notice':None}
    key=current_release_key()
    state=_slot(request,key,create=True)
    if state is None:return {'release_notice':None}
    if state['dismissed']:return {'release_notice':None}
    available=True
    try:
        seen=ReleaseNoticeAcknowledgement.objects.filter(user_id=request.user.pk,release_key=key).exists()
    except DatabaseError:
        logger.warning('release_notice.storage_unavailable')
        available=False
        seen=False
    if seen:
        request.session[SESSION_KEY]={**state,'dismissed':True,'remembered':True}
        return {'release_notice':None}
    return {'release_notice':{**NOTES,'changes':list(NOTES['changes']),'release_id':key,
        'version':key[:7] if key!=LOCAL_RELEASE_KEY else 'Local development',
        'ack_url':ack_url,'cache_nonce':state['nonce'],
        'actor_key':state['actor_key'],'storage_available':available}}


def _json_pairs(pairs):
    data={}
    for key,value in pairs:
        if key in data:raise ValueError('Duplicate JSON key')
        data[key]=value
    return data


def _response(status,code,message,**extra):
    response=JsonResponse({'ok':status==200,'code':code,'message':message,**extra},status=status)
    response['Cache-Control']='private, no-store'
    return response


@never_cache
@login_required(login_url='/login/')
@require_POST
def acknowledge(request):
    try:
        if not _eligible(request):return _response(403,'access_denied','Sign in with an active application account.')
    except DatabaseError:
        return _response(503,'save_unavailable','Your choice could not be saved. Retry, or continue for this login.')
    try:
        length=request.META.get('CONTENT_LENGTH','')
        if length and (not length.isascii() or not length.isdigit() or len(length)>10 or int(length)>4096):raise ValueError()
        if request.content_type!='application/json' or len(request.body)>4096:raise ValueError()
        data=json.loads(request.body.decode('utf-8'),object_pairs_hook=_json_pairs)
        if not isinstance(data,dict) or set(data)!={'release_id','session_nonce','suppress_current'}:raise ValueError()
        key=data['release_id'];nonce=data['session_nonce'];remember=data['suppress_current']
        if (not isinstance(key,str) or len(key)>80 or not RELEASE.fullmatch(key)
                or not isinstance(nonce,str) or not TOKEN.fullmatch(nonce) or type(remember) is not bool):raise ValueError()
    except (ValueError,TypeError,UnicodeError):
        return _response(400,'invalid_request','Refresh this update notice and try again.')
    if key!=current_release_key():
        return _response(409,'release_changed','A different update is now installed. Refresh to read its notice.')
    state=_slot(request,key)
    if state is None or not secrets.compare_digest(state['nonce'],nonce):
        return _response(409,'session_changed','Your login or notice changed. Refresh before saving this choice.')
    try:
        with transaction.atomic():
            if remember:
                ReleaseNoticeAcknowledgement.objects.get_or_create(user_id=request.user.pk,release_key=key)
                remembered=True
            else:
                remembered=ReleaseNoticeAcknowledgement.objects.filter(user_id=request.user.pk,release_key=key).exists()
    except DatabaseError:
        return _response(503,'save_unavailable','Your choice could not be saved. Retry, or continue for this login.')
    request.session[SESSION_KEY]={**state,'dismissed':True,'remembered':remembered}
    return _response(200,'saved','This update is remembered.' if remembered else 'Hidden for this login only.',
        release_id=key,dismissal='remembered' if remembered else 'session_only')
