"""Retained legacy attachments require the same project checks as their record.

This is not a media-directory proxy. The requested name must be an exact saved
attachment of the authorised checklist, and resolved files must stay in MEDIA_ROOT.
Modern photo, document, branding and drawing views retain their stricter rules.
"""
import mimetypes
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET


def _name(value):
    if not isinstance(value, str) or '\\' in value or '\x00' in value:
        raise Http404()
    if value.startswith('/media/'):
        value = value[len('/media/'):]
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ':' in value or any(part in {'..', '.'} for part in value.split('/')):
        raise Http404()
    return value


def attachment_names(checklist):
    names = []
    for paths in (checklist.image_data or {}).values():
        if isinstance(paths, list):
            names.extend(value for value in paths if isinstance(value, str))
    names.extend(checklist.images.values_list('image', flat=True))
    if checklist.template_copy:
        names.append(checklist.template_copy.name)
    zip_info = (checklist.answer_data or {}).get('zip_upload')
    if isinstance(zip_info, dict) and isinstance(zip_info.get('path'), str):
        names.append(zip_info['path'])
    result = set()
    for value in names:
        try:
            result.add(_name(value))
        except Http404:
            # Retain malformed historical references without exposing other files.
            continue
    return result


@require_GET
def checklist_file(request, checklist_id):
    from .access import role_for
    from .account_views import legacy_survey_access
    from .models import Profile
    if role_for(request.user) == Profile.Roles.SUPER_ADMIN:
        raise Http404()
    checklist = legacy_survey_access(request, checklist_id)['checklist']
    name = _name(request.GET.get('path', ''))
    if name not in attachment_names(checklist):
        raise Http404()
    media = Path(settings.MEDIA_ROOT).resolve()
    path = (media / name).resolve()
    if not path.is_relative_to(media) or not path.is_file():
        raise Http404()
    content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    inline = content_type in {'image/jpeg', 'image/png', 'image/webp'}
    response = FileResponse(path.open('rb'), content_type=content_type if inline else 'application/octet-stream',
                            as_attachment=not inline, filename=path.name)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
