"""Record a version once on authenticated login; never write on history GET."""
import logging
import re
from datetime import date
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError,transaction
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .access import is_super_admin
from .release_history_models import InstalledRelease


def validate_version(value):
    if not isinstance(value,str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})(?:\.(?:0|[1-9][0-9]{0,3}))?',value):
        raise ValueError('Use major.minor or major.minor.patch version numbers.')
    return value


@transaction.atomic
def register_current_release():
    from .release_notice import current_release_key
    from .release_note_content import NOTES
    key=current_release_key();version=validate_version(NOTES['version'])
    defaults={'version':version,'title':NOTES['title'],'release_date':date.fromisoformat(NOTES['date']),
              'changes':list(NOTES['changes'])}
    record,created=InstalledRelease.objects.get_or_create(release_key=key,defaults=defaults)
    if not created and any(getattr(record,field)!=value for field,value in defaults.items()):
        raise ValueError('Installed release identity already has different notes; use a new release identity.')
    return record,created


def record_login_release(sender,request,user,**kwargs):
    if not user.is_active:return
    try:register_current_release()
    except (DatabaseError,ValueError):
        # Optional history availability must never defeat authentication.
        logging.getLogger(__name__).warning('release_history.registration_unavailable')


@login_required
@never_cache
@require_GET
def release_history(request):
    if not is_super_admin(request.user):raise PermissionDenied('Release history requires platform administration.')
    page=Paginator(InstalledRelease.objects.all(),25).get_page(request.GET.get('page'))
    return render(request,'dashboards/release_history.html',{'releases':page,'active_view':'release_history'})
