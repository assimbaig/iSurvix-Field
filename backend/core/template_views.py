"""Admin checklist designer and the version-bound engineer survey form."""
import json
from io import BytesIO

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from PIL import Image, UnidentifiedImageError

from .models import Checklist, ChecklistTemplate, Profile, Project, WorkAssignment
from .template_service import default_definition, duplicate_revision, export_custom_excel, field_map, missing_required, validate_answer, validate_definition


def is_template_admin(request):
    return request.user.is_authenticated and (request.user.is_superuser or getattr(getattr(request.user, 'profile', None), 'role', None) == Profile.Roles.ADMIN)


def image_bytes(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Images must be 5 MB or smaller.')
    try:
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in {'PNG', 'JPEG', 'WEBP'}:
            raise ValidationError('Use a PNG, JPEG, or WebP image.')
        if image.width * image.height > 24000000:
            raise ValidationError('Image dimensions are too large.')
        image = image.convert('RGBA' if image.mode == 'RGBA' else 'RGB')
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError('The uploaded file is not a valid image.')


@require_http_methods(['GET', 'POST'])
def template_builder(request, template_id=None):
    if not is_template_admin(request):
        return HttpResponse('Admin access required.', status=403)
    template = get_object_or_404(ChecklistTemplate, pk=template_id) if template_id else None
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action in {'create_original', 'create_blank'}:
                definition = default_definition() if action == 'create_original' else {'title': 'Custom checklist', 'sections': [{'id': 'general', 'title': 'General information', 'fields': [{'id': 'site_id', 'label': 'Site ID', 'type': 'text', 'system': 'site_id', 'required': True}]}]}
                template = ChecklistTemplate.objects.create(name=definition['title'], definition=definition, created_by=request.user)
                if action == 'create_original':
                    from pathlib import Path
                    from django.conf import settings
                    for slot, filename in [('left', 'nokia.png'), ('right', 'tawal.png')]:
                        logo = Path(settings.BASE_DIR) / 'static' / 'core' / 'img' / filename
                        if logo.exists():
                            getattr(template, f'client_{slot}_logo').save(filename, ContentFile(logo.read_bytes()), save=False)
                    template.save()
                return redirect('checklist_template_edit', template_id=template.id)
            if not template:
                raise ValidationError('Choose a checklist template first.')
            if action == 'duplicate':
                template = duplicate_revision(template, request.user)
                return redirect('checklist_template_edit', template_id=template.id)
            if action == 'assign':
                if not template.published:
                    raise ValidationError('Publish this revision before assigning it to a project.')
                project = get_object_or_404(Project, pk=request.POST.get('project_id'))
                project.checklist_template = template
                project.save(update_fields=['checklist_template'])
                messages.success(request, 'Assigned to the project. Existing surveys retain their previous template.')
            elif action in {'save', 'publish'}:
                if template.published:
                    raise ValidationError('Published revisions are locked. Duplicate this revision to edit.')
                definition = json.loads(request.POST.get('definition', '{}'))
                validate_definition(definition)
                name = request.POST.get('name', '').strip()
                if not name or len(name) > 160:
                    raise ValidationError('Provide a template name of at most 160 characters.')
                # Verify all files before storing or mutating the revision.
                uploads = {slot: image_bytes(request.FILES[slot]) for slot in ['client_left_logo', 'client_right_logo'] if slot in request.FILES}
                with transaction.atomic():
                    template = ChecklistTemplate.objects.select_for_update().get(pk=template.pk)
                    if template.published:
                        raise ValidationError('This revision was published in another window. Duplicate it to edit.')
                    template.name, template.definition = name, definition
                    for slot in ['left', 'right']:
                        setattr(template, f'client_{slot}_name', request.POST.get(f'client_{slot}_name', '').strip()[:80])
                        attr = f'client_{slot}_logo'
                        if request.POST.get(f'remove_{attr}') == 'on':
                            setattr(template, attr, '')
                        if attr in uploads:
                            getattr(template, attr).save(f'client-{slot}.png', ContentFile(uploads[attr]), save=False)
                    template.published = action == 'publish'
                    template.save()
                messages.success(request, 'Revision published and locked.' if template.published else 'Draft saved.')
            else:
                raise ValidationError('Unknown template action.')
            return redirect('checklist_template_edit', template_id=template.id)
        except (ValidationError, ValueError, TypeError) as error:
            messages.error(request, '; '.join(error.messages) if isinstance(error, ValidationError) else 'Invalid template data.')
    return render(request, 'dashboards/template_builder.html', {'templates': ChecklistTemplate.objects.all(), 'selected_template': template, 'definition': template.definition if template else None, 'projects': Project.objects.all()})


@require_http_methods(['GET'])
def template_logo(request, template_id, slot):
    if not is_template_admin(request):
        return HttpResponse(status=403)
    template = get_object_or_404(ChecklistTemplate, pk=template_id)
    if slot not in ['left', 'right']:
        raise Http404()
    logo = getattr(template, f'client_{slot}_logo')
    if not logo or not default_storage.exists(logo.name):
        raise Http404()
    response = FileResponse(default_storage.open(logo.name, 'rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response


def survey_access(request, checklist_id, edit=False):
    if not request.user.is_authenticated:
        raise Http404()
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    profile = getattr(request.user, 'profile', None)
    admin = is_template_admin(request)
    owner = checklist.user_id == request.user.id and profile and profile.project_id == checklist.project_id
    lead = profile and profile.role == Profile.Roles.TEAM_LEAD and profile.project_id == checklist.project_id
    if not checklist.schema_snapshot or not (admin or owner or lead):
        raise Http404()
    if edit and checklist.status == Checklist.Status.FINAL:
        raise ValidationError('This approved checklist is locked.')
    return {'checklist': checklist, 'can_edit': checklist.status != Checklist.Status.FINAL, 'role': 'ADMIN' if admin else profile.role, 'redirect': None}


def field_is_locked(checklist, field_id):
    return checklist.status == Checklist.Status.FINAL or any(
        section['id'] in checklist.section_approvals and any(f['id'] == field_id for f in section['fields'])
        for section in checklist.schema_snapshot['sections'])


def require_field_editable(checklist, field_id):
    if field_is_locked(checklist, field_id):
        raise ValidationError('This section is approved and locked.')


@require_http_methods(['POST'])
def custom_review(request, checklist_id):
    access = survey_access(request, checklist_id)
    if access['role'] not in ['ADMIN', Profile.Roles.TEAM_LEAD]:
        return HttpResponse(status=403)
    try:
        action = request.POST.get('action', '')
        note = request.POST.get('comment', '').strip()
        if action not in {'approve', 'partial', 'reject', 'changes'}:
            raise ValidationError('Choose a review decision.')
        if action in {'reject', 'changes'} and not note:
            raise ValidationError('A reason is required.')
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status not in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]:
                raise ValidationError('Only submitted surveys can be reviewed.')
            sections = {s['id']: s for s in checklist.schema_snapshot['sections']}
            chosen = list(dict.fromkeys(request.POST.getlist('sections')))
            if action == 'approve':
                chosen = list(sections)
            if action == 'partial' and (not chosen or any(s not in sections or s in checklist.section_approvals for s in chosen)):
                raise ValidationError('Select one or more pending sections.')
            if action in {'approve', 'partial'}:
                from copy import copy
                candidate = copy(checklist)
                candidate.schema_snapshot = {**checklist.schema_snapshot, 'sections': [sections[s] for s in chosen]}
                if missing_required(candidate):
                    raise ValidationError('Complete required fields in the selected sections before approval.')
                approvals = dict(checklist.section_approvals)
                for sid in chosen:
                    approvals[sid] = {'by': request.user.pk, 'name': request.user.username, 'time': timezone.now().isoformat()}
                checklist.section_approvals = approvals
                checklist.status = Checklist.Status.FINAL if all(s in approvals for s in sections) else Checklist.Status.PARTIAL
            elif action == 'reject':
                checklist.section_approvals = {}
                checklist.status = Checklist.Status.REJECTED
                chosen = []
            else:
                checklist.status = Checklist.Status.DRAFT
                chosen = []
            checklist.comment, checklist.comment_by = note, request.user
            checklist.review_history = [*checklist.review_history, {'action': action, 'sections': chosen, 'comment': note, 'by': request.user.pk, 'name': request.user.username, 'time': timezone.now().isoformat()}]
            checklist.save(update_fields=['status', 'section_approvals', 'review_history', 'comment', 'comment_by', 'updated_at'])
            if checklist.status == Checklist.Status.FINAL:
                WorkAssignment.objects.filter(checklist=checklist).update(status=WorkAssignment.Status.COMPLETED, completed_at=timezone.now())
        messages.success(request, 'Review recorded. Approved sections are locked.')
    except ValidationError as error:
        messages.error(request, '; '.join(error.messages))
    return redirect('custom_checklist', checklist_id=checklist_id)


def survey_context(checklist, request):
    from django.urls import reverse
    answers = (checklist.answer_data or {}).get('custom', {})
    sections = []
    for section in checklist.schema_snapshot['sections']:
        fields = []
        for field in section['fields']:
            value = checklist.site_id if field.get('system') == 'site_id' else answers.get(field['id'], '')
            f = {**field, 'locked': field_is_locked(checklist, field['id']), 'value': value, 'images': [{'path': p, 'url': reverse('custom_checklist_photo', args=[checklist.id, field['id'], i])} for i, p in enumerate((checklist.image_data or {}).get(field['id'], []))]}
            if field['type'] == 'inspection':
                f['result'] = value.get('result', '') if isinstance(value, dict) else ''
                f['remarks'] = value.get('remarks', '') if isinstance(value, dict) else ''
            if field['type'] == 'table':
                rows = value if isinstance(value, list) else []
                f['rows'] = [[row.get(c['id'], '') for c in field['columns']] for row in rows]
            fields.append(f)
        sections.append({**section, 'locked': checklist.status == Checklist.Status.FINAL or section['id'] in checklist.section_approvals, 'fields': fields})
    return sections


@require_http_methods(['GET'])
def custom_survey(request, checklist_id):
    access = survey_access(request, checklist_id)
    checklist = access['checklist']
    return render(request, 'dashboards/custom_checklist.html', {'checklist': checklist, 'sections': survey_context(checklist, request), 'schema': checklist.schema_snapshot, 'can_edit': access.get('can_edit') and checklist.status != Checklist.Status.FINAL, 'can_review': access.get('role') in ['ADMIN', Profile.Roles.TEAM_LEAD], 'can_manage_templates': is_template_admin(request), 'missing': missing_required(checklist), 'can_decide': checklist.status in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]})


@require_http_methods(['POST'])
def custom_save(request, checklist_id):
    try:
        survey_access(request, checklist_id, edit=True)
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or not isinstance(payload.get('answers'), dict):
            raise ValidationError('Provide an answers object.')
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status == Checklist.Status.FINAL:
                raise ValidationError('This approved checklist is locked.')
            fields = field_map(checklist)
            answers = dict((checklist.answer_data or {}).get('custom', {}))
            for fid, value in payload['answers'].items():
                if fid not in fields:
                    raise ValidationError('A field is not part of this survey revision.')
                field = fields[fid]
                if field.get('system') == 'site_id':
                    if value != checklist.site_id:
                        raise ValidationError('Change Site ID through the assignment record.')
                    continue
                if field_is_locked(checklist, fid):
                    if value != answers.get(fid, ''):
                        raise ValidationError('This section is approved and locked.')
                    continue
                validate_answer(field, value)
                answers[fid] = value
            checklist.answer_data = {**(checklist.answer_data or {}), 'custom': answers}
            checklist.save(update_fields=['answer_data', 'updated_at'])
        return JsonResponse({'status': 'success', 'missing': missing_required(checklist), 'can_decide': checklist.status in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]})
    except (ValidationError, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid field value, missing N/A reason, or locked checklist.'}, status=400)


@require_http_methods(['POST'])
def custom_upload(request, checklist_id, field_id):
    try:
        access = survey_access(request, checklist_id, edit=True)
        if field_id not in field_map(access['checklist']):
            raise ValidationError('Unknown evidence field.')
        uploads = request.FILES.getlist('images')
        if not 1 <= len(uploads) <= 20:
            raise ValidationError('Upload between 1 and 20 photos at a time.')
        verified = [image_bytes(upload) for upload in uploads]
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status == Checklist.Status.FINAL:
                raise ValidationError('This approved checklist is locked.')
            require_field_editable(checklist, field_id)
            all_images = dict(checklist.image_data or {})
            existing = list(all_images.get(field_id, []))
            if sum(len(p) for p in all_images.values()) + len(verified) > 200:
                raise ValidationError('This survey supports up to 200 photographs.')
            for image in verified:
                import uuid
                path = default_storage.save(f'custom_evidence/{checklist.id}/{field_id}/{uuid.uuid4().hex}.png', ContentFile(image))
                existing.append(path)
            all_images[field_id] = existing
            checklist.image_data = all_images
            checklist.save(update_fields=['image_data', 'updated_at'])
        return JsonResponse({'status': 'success'})
    except ValidationError as error:
        return JsonResponse({'status': 'error', 'message': '; '.join(error.messages)}, status=400)


@require_http_methods(['GET'])
def custom_photo(request, checklist_id, field_id, index):
    checklist = survey_access(request, checklist_id)['checklist']
    paths = (checklist.image_data or {}).get(field_id, [])
    if index >= len(paths) or not default_storage.exists(paths[index]):
        raise Http404()
    response = FileResponse(default_storage.open(paths[index], 'rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response


@require_http_methods(['POST'])
def custom_photo_delete(request, checklist_id, field_id, index):
    try:
        survey_access(request, checklist_id, edit=True)
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status == Checklist.Status.FINAL:
                raise ValidationError('This approved checklist is locked.')
            require_field_editable(checklist, field_id)
            images = dict(checklist.image_data or {})
            paths = list(images.get(field_id, []))
            if index >= len(paths):
                raise Http404()
            # Remove the association atomically; keep evidence bytes for recovery.
            paths.pop(index)
            images[field_id] = paths
            checklist.image_data = images
            checklist.save(update_fields=['image_data', 'updated_at'])
        return JsonResponse({'status': 'success'})
    except ValidationError:
        return JsonResponse({'status': 'error', 'message': 'This approved checklist is locked.'}, status=400)


@require_http_methods(['GET'])
def custom_client_logo(request, checklist_id, slot):
    checklist = survey_access(request, checklist_id)['checklist']
    clients = checklist.branding_snapshot.get('clients', [])
    if slot >= len(clients) or not clients[slot].get('logo') or not default_storage.exists(clients[slot]['logo']):
        raise Http404()
    response = FileResponse(default_storage.open(clients[slot]['logo'], 'rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response


@require_http_methods(['POST'])
def custom_submit(request, checklist_id):
    try:
        access = survey_access(request, checklist_id, edit=True)
        if request.user != access['checklist'].user and access.get('role') != 'ADMIN':
            return HttpResponse(status=403)
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status == Checklist.Status.FINAL:
                raise ValidationError('This approved checklist is locked.')
            missing = missing_required(checklist)
            if missing:
                raise ValidationError('Complete required fields: '+', '.join(missing))
            checklist.status = Checklist.Status.PARTIAL if checklist.section_approvals else Checklist.Status.SUBMITTED
            checklist.save(update_fields=['status', 'updated_at'])
            WorkAssignment.objects.filter(checklist=checklist).update(status=WorkAssignment.Status.SUBMITTED, submitted_at=timezone.now())
        messages.success(request, 'Checklist submitted for review.')
    except ValidationError as error:
        messages.error(request, '; '.join(error.messages))
    return redirect('custom_checklist', checklist_id=checklist_id)


@require_http_methods(['GET'])
def custom_download(request, checklist_id):
    checklist = survey_access(request, checklist_id)['checklist']
    content = export_custom_excel(checklist)
    response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    from django.utils.text import slugify
    filename = slugify(checklist.site_id) or f'survey-{checklist.id}'
    response['Content-Disposition'] = f'attachment; filename="{filename}-checklist.xlsx"'
    response['Cache-Control'] = 'private, no-store'
    return response
