"""Admin checklist designer and the version-bound engineer survey form."""
import json
import re
from io import BytesIO

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from PIL import Image, UnidentifiedImageError

from .models import Checklist, ChecklistTemplate, Profile, Project, WorkAssignment
from .template_service import default_definition, duplicate_revision, export_custom_excel, field_map, missing_required, validate_answer, validate_definition


def is_template_admin(request):
    from .access import is_super_admin,role_for,accessible_projects
    return not is_super_admin(request.user) and role_for(request.user)==Profile.Roles.ADMIN and accessible_projects(request.user).exists()


def template_scope(user):
    from .access import is_super_admin,role_for,managed_project_ids
    if is_super_admin(user):
        return ChecklistTemplate.objects.none()
    if role_for(user)!=Profile.Roles.ADMIN:
        return ChecklistTemplate.objects.none()
    projects=managed_project_ids(user)
    if not projects.exists():
        return ChecklistTemplate.objects.none()
    personal=Q(created_by=user,projects__isnull=True,checklists__isnull=True)
    return ChecklistTemplate.objects.filter(personal|Q(projects__pk__in=projects)|Q(checklists__project_id__in=projects)).distinct()


def project_scope(user):
    from .access import accessible_projects
    return accessible_projects(user)


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
@never_cache
def template_builder(request, template_id=None, wizard_mode=False):
    if not is_template_admin(request):
        return HttpResponse('Admin access required.', status=403)
    if template_id is None and (request.method == 'GET' or request.POST.get('action') in {'unpublish','delete','disable','enable'}):
        from .checklist_wizard_views import library
        return library(request)
    template = get_object_or_404(template_scope(request.user), pk=template_id) if template_id else None
    route = 'checklist_wizard_edit' if wizard_mode else 'checklist_template_edit'
    submitted_definition = None
    editor_unsaved = False
    stored_assets = []
    response_status = 200
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            if action in {'create_original', 'create_blank'}:
                definition = default_definition() if action == 'create_original' else {'title': 'Custom checklist', 'sections': [{'id': 'general', 'title': 'General information', 'fields': [{'id': 'site_id', 'label': 'Site ID', 'type': 'text', 'system': 'site_id', 'required': True}]}]}
                template = ChecklistTemplate.objects.create(name=definition['title'], definition=definition, created_by=request.user,
                    client_left_name='',client_right_name='')
                return redirect(route, template_id=template.id)
            if not template:
                raise ValidationError('Choose a checklist template first.')
            if request.POST.get('editor_template_id') not in (None,str(template.pk)) or request.POST.get('editor_version') not in (None,str(template.version)):
                response_status=409
                raise ValidationError('The submitted checklist or revision does not match this editor. Reopen the intended draft.')
            if action == 'duplicate':
                template = duplicate_revision(template, request.user)
                return redirect(route, template_id=template.id)
            if action == 'assign':
                if not template.published or template.disabled:
                    raise ValidationError('Publish this revision before assigning it to a project.')
                project = get_object_or_404(project_scope(request.user), pk=request.POST.get('project_id'))
                project.checklist_template = template
                project.save(update_fields=['checklist_template'])
                messages.success(request, 'Assigned to the project. Existing surveys retain their previous template.')
            elif action in {'save', 'publish'}:
                from .access import is_super_admin
                from .checklist_lifecycle import require_editable
                require_editable(request.user,template)
                if template.published or template.disabled or template.checklists.exists():
                    raise ValidationError('Published revisions are locked. Duplicate this revision to edit.')
                definition = json.loads(request.POST.get('definition', '{}'))
                validate_definition(definition)
                scoped_definition=wizard_mode or 'wizard_context' in template.definition or 'standard_catalog' in template.definition
                if scoped_definition:
                    from .checklist_wizard_service import source_identity,identity
                    context=source_identity(template,request.user)
                    expected_context=identity(request.user,context['industry'],context['workflow_type'])
                    if definition.get('wizard_context') not in (None,expected_context):
                        raise ValidationError('The industry and workflow cannot change while editing this draft.')
                    if 'standard_catalog' in template.definition and 'standard_catalog' not in definition:
                        raise ValidationError('Keep the source standard configuration when editing its draft.')
                    definition['wizard_context']=expected_context
                    validate_definition(definition)
                # A later name/logo/storage error must not discard a valid tree.
                # This remains an in-memory render candidate until save succeeds.
                submitted_definition = definition
                name = request.POST.get('name', '').strip()
                if not name or len(name) > 160:
                    raise ValidationError('Provide a template name of at most 160 characters.')
                # Verify all files before storing or mutating the revision.
                uploads = {slot: image_bytes(request.FILES[slot]) for slot in ['client_left_logo', 'client_right_logo', 'company_logo'] if slot in request.FILES}
                with transaction.atomic():
                    if scoped_definition:
                        from .governance_views import lock_governance
                        from .checklist_wizard_service import guard
                        lock_governance(request.user);guard(request.user,True)
                        if not template_scope(request.user).filter(pk=template.pk).exists():
                            raise PermissionDenied('This draft is no longer in your permitted project scope.')
                    template = ChecklistTemplate.objects.select_for_update().get(pk=template.pk)
                    require_editable(request.user,template)
                    if wizard_mode or 'wizard_expected_digest' in request.POST:
                        from .checklist_wizard_service import digest,guard
                        guard(request.user,True)
                        expected=request.POST.get('wizard_expected_digest')
                        if expected != template_edit_digest(template):
                            submitted_definition=definition
                            response_status=409
                            raise ValidationError('This draft changed in another window. Your entered structure is retained below. Reload the current draft before saving again.')
                    if template.published or template.disabled or template.checklists.exists():
                        raise ValidationError('This revision was published in another window. Duplicate it to edit.')
                    template.name, template.definition = name, definition
                    if request.POST.get('processing_setting_present') == '1':
                        template.checklist_required = request.POST.get('checklist_required') == 'on'
                    if request.POST.get('remove_company_logo') == 'on':
                        template.company_logo = ''
                    if 'company_logo' in uploads:
                        template.company_logo.save('company.png', ContentFile(uploads['company_logo']), save=False)
                        stored_assets.append(template.company_logo.name)
                    for slot in ['left', 'right']:
                        if f'client_{slot}_name' in request.POST:
                            setattr(template, f'client_{slot}_name', request.POST.get(f'client_{slot}_name', '').strip()[:80])
                        attr = f'client_{slot}_logo'
                        if request.POST.get(f'remove_{attr}') == 'on':
                            setattr(template, attr, '')
                        if attr in uploads:
                            getattr(template, attr).save(f'client-{slot}.png', ContentFile(uploads[attr]), save=False)
                            stored_assets.append(getattr(template, attr).name)
                    template.published = action == 'publish'
                    template.save()
                messages.success(request, 'Revision published and locked.' if template.published else 'Draft saved.')
            else:
                raise ValidationError('Unknown template action.')
            return redirect(route, template_id=template.id)
        except (ValidationError, ValueError, TypeError, OSError) as error:
            # Filesystem writes do not participate in the database transaction.
            # Remove only newly written files from this failed request; retain
            # every previously configured logo and the user's unsaved controls.
            for name in stored_assets:
                try:
                    default_storage.delete(name)
                except OSError:
                    pass
            if template:
                template.refresh_from_db()
            response_status = 409 if response_status == 409 else 400
            editor_unsaved = submitted_definition is not None
            explanation = '; '.join(error.messages) if isinstance(error, ValidationError) else 'Local storage is unavailable. Your entered changes remain unsaved; reselect replacement logo files before retrying.' if isinstance(error, OSError) else 'Invalid template data.'
            messages.error(request, explanation)
    token=template_edit_digest(template) if template else ''
    if response_status==409:
        # Keep the stale token: retry must never silently overwrite a newer draft.
        token=request.POST.get('wizard_expected_digest','')
    if editor_unsaved:
        from copy import copy
        template=copy(template)
        template.name=request.POST.get('name',template.name)
        if request.POST.get('processing_setting_present') == '1':
            template.checklist_required=request.POST.get('checklist_required') == 'on'
        for slot in ('left','right'):
            setattr(template,f'client_{slot}_name',request.POST.get(f'client_{slot}_name',getattr(template,f'client_{slot}_name')))
    from .access import company_id_for
    from .models import Company
    company=Company.objects.filter(pk=company_id_for(request.user)).first()
    return render(request, 'dashboards/template_builder.html', {'templates': template_scope(request.user), 'selected_template': template, 'template_locked':bool(template and (template.published or template.disabled or template.checklists.exists())), 'definition': submitted_definition if submitted_definition is not None else template.definition if template else None, 'projects': project_scope(request.user), 'wizard_mode':wizard_mode,'wizard_step':3 if template and template.published else 2,'wizard_expected_digest':token,'editor_company_name':company.name if company else 'Company','active_view':'checklists','editor_unsaved':editor_unsaved},status=response_status)


@require_http_methods(['GET'])
@never_cache
def template_recommendations(request,template_id):
    if not is_template_admin(request):return JsonResponse({'message':'Project Admin access required.'},status=403)
    template=get_object_or_404(template_scope(request.user),pk=template_id)
    try:
        from .editor_recommendations import additions
        result=additions(request.user,template)
        result['locked']=bool(template.published or template.disabled or template.checklists.exists())
        return JsonResponse(result)
    except (ValidationError,ValueError) as error:
        return JsonResponse({'message':'; '.join(error.messages) if isinstance(error,ValidationError) else str(error),'recommendations':[]},status=422)


def template_edit_digest(template):
    from .checklist_wizard_service import digest
    return digest({'name':template.name,'definition':template.definition,'published':template.published,'disabled':template.disabled,'checklist_required':template.checklist_required,
                   'version':template.version,'left_name':template.client_left_name,'right_name':template.client_right_name,
                   'left_logo':template.client_left_logo.name,'right_logo':template.client_right_logo.name,'company_logo':template.company_logo.name})


@require_http_methods(['GET'])
def template_logo(request, template_id, slot):
    if not is_template_admin(request):
        return HttpResponse(status=403)
    template = get_object_or_404(template_scope(request.user), pk=template_id)
    if slot not in ['left', 'right', 'company']:
        raise Http404()
    logo = template.company_logo if slot == 'company' else getattr(template, f'client_{slot}_logo')
    if not logo or not default_storage.exists(logo.name):
        raise Http404()
    response = FileResponse(default_storage.open(logo.name, 'rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response


def survey_access(request, checklist_id, edit=False):
    from .access import is_super_admin,can_access_project
    if not request.user.is_authenticated or not request.user.is_active:
        raise Http404()
    if is_super_admin(request.user):
        raise PermissionDenied('Super Admin manages administration only; engineering records require an operational role.')
    checklist = get_object_or_404(Checklist, pk=checklist_id)
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_locked:
        raise Http404()
    # Category intake freezes Engineer sources for every governance mode. QA
    # edits its version-bound overlay; reviewer/admin legacy aliases must not
    # reopen raw answers or point evidence on a submitted category record.
    from .category_intake import enabled as category_enabled,access as capture_access
    category_editable=None
    if category_enabled(checklist):
        if profile and profile.role==Profile.Roles.CLIENT:
            category_editable=False
            if edit:raise PermissionDenied('Submitted category evidence is read-only.')
        else:
            checklist,capture_flags=capture_access(request,checklist_id,edit=edit)
            category_editable=capture_flags['can_edit']
    from .independent_workflow import is_independent,assigned_site_access,is_frozen
    if is_independent(checklist):
        from .access import role_for
        if not assigned_site_access(request.user,checklist):
            raise Http404()
        can_edit=category_editable if category_editable is not None else role_for(request.user)==Profile.Roles.ENGINEER and checklist.user_id==request.user.pk and checklist.status in {Checklist.Status.DRAFT,Checklist.Status.REJECTED} and not is_frozen(checklist)
        if edit and not can_edit:
            raise PermissionDenied('This governed revision is frozen or outside your assigned capture stage.')
        return {'checklist':checklist,'can_edit':can_edit,'role':role_for(request.user),'redirect':None}
    admin = is_super_admin(request.user) or bool(profile and profile.role == Profile.Roles.ADMIN and can_access_project(request.user,checklist.project_id))
    owner = checklist.user_id == request.user.id and profile and profile.role == Profile.Roles.ENGINEER and can_access_project(request.user,checklist.project_id)
    lead = profile and profile.role == Profile.Roles.TEAM_LEAD and can_access_project(request.user,checklist.project_id)
    quality = profile and profile.role == Profile.Roles.QUALITY_ENGINEER and checklist.quality_reviewer_id==request.user.pk and can_access_project(request.user,checklist.project_id)
    client = profile and profile.role == Profile.Roles.CLIENT and can_access_project(request.user,checklist.project_id) and checklist.status == Checklist.Status.FINAL
    if not checklist.schema_snapshot or not (admin or owner or lead or client or quality):
        raise Http404()
    if edit and (client or quality):
        raise PermissionDenied('Clients may review final evidence and record a client decision only.')
    can_edit = not (client or quality) and checklist.status != Checklist.Status.FINAL
    if profile and profile.role == Profile.Roles.ENGINEER and not is_super_admin(request.user):
        can_edit = can_edit and checklist.status in [Checklist.Status.DRAFT, Checklist.Status.REJECTED, Checklist.Status.PARTIAL]
    if category_editable is not None:can_edit=category_editable
    if edit and not can_edit:
        raise ValidationError('This approved checklist is locked.')
    return {'checklist': checklist, 'can_edit': can_edit, 'role': 'ADMIN' if admin else profile.role, 'redirect': None}


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
    from .independent_workflow import is_independent,policy_for,review_revision
    from .access import role_for
    if is_independent(access['checklist']):
        from django.urls import reverse
        return HttpResponse('Use the revision-bound activity review: '+reverse('roadmap_activity',args=[checklist_id]),status=409)
    if role_for(request.user)!=Profile.Roles.TEAM_LEAD:
        return HttpResponse(status=403)
    try:
        action = request.POST.get('action', '')
        note = request.POST.get('comment', '').strip()
        if action not in {'approve', 'partial', 'reject', 'changes'}:
            raise ValidationError('Choose a review decision.')
        if action in {'reject', 'changes'} and not note:
            raise ValidationError('A reason is required.')
        with transaction.atomic():
            from .governance_views import lock_governance
            lock_governance(request.user)
            refreshed=survey_access(request,checklist_id)
            if role_for(request.user)!=Profile.Roles.TEAM_LEAD:
                return HttpResponse(status=403)
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status not in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]:
                raise ValidationError('Only submitted surveys can be reviewed.')
            from .quality_workflow import quality_is_current
            if not quality_is_current(checklist):
                raise ValidationError('Quality Control approval of the current submitted evidence is required before Team Lead review.')
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
                if missing_required(candidate, evidence_checklist=checklist):
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
            from .governance_views import audit
            audit(request.user, 'survey_review', checklist.project, checklist_id=checklist.pk,
                  decision=action, sections=chosen)
            from .workflow_service import internal_review_completed
            internal_review_completed(checklist,request.user)
        messages.success(request, 'Review recorded. Approved sections are locked.')
    except ValidationError as error:
        messages.error(request, '; '.join(error.messages))
    return redirect('custom_checklist', checklist_id=checklist_id)


def survey_context(checklist, request):
    from .category_intake import projected_checklist
    checklist=projected_checklist(checklist)
    from django.urls import reverse
    from collections import defaultdict
    from .field_photo_service import placements
    linked=defaultdict(list)
    proposed=defaultdict(list)
    for placement in placements(checklist):
        image={'url':reverse('photo_evidence',args=[checklist.pk,placement.photo_id,'preview']),
               'source_url':reverse('photo_evidence',args=[checklist.pk,placement.photo_id,'original']),
               'filename':placement.photo.filename,'photo_id':placement.photo_id,
               'placement_id':placement.pk,'status':placement.status,'reason':re.sub(r'metadata', 'AI Analysis', placement.reason or '', flags=re.I)}
        if placement.status in {'confirmed','manual'}:
            linked[placement.field_id].append(image)
        elif placement.status=='proposed':
            proposed[placement.field_id].append(image)
    answers = (checklist.answer_data or {}).get('custom', {})
    from .field_intake_service import site_information_fields
    general_context = {f['id']: f for f in site_information_fields(checklist)}
    actor = getattr(request, 'user', None)
    allow_prefill = bool(actor and actor.is_authenticated and survey_access(request, checklist.pk).get('can_edit')) and checklist.status != Checklist.Status.FINAL
    sections = []
    for section in checklist.schema_snapshot['sections']:
        fields = []
        for field in section['fields']:
            value = checklist.site_id if field.get('system') == 'site_id' else answers.get(field['id'], '')
            f = {**field, 'locked': field_is_locked(checklist, field['id']), 'value': value, 'images': [{'path': p, 'url': reverse('custom_checklist_photo', args=[checklist.id, field['id'], i])} for i, p in enumerate((checklist.image_data or {}).get(field['id'], []))]}
            hint = general_context.get(field['id'], {})
            f.update({key: hint.get(key) for key in ('suggested_value', 'suggestion_source', 'suggestion_note', 'suggestion_conflict')})
            f['prefilled'] = bool(allow_prefill and hint.get('prefilled') and not f['locked'])
            if f['prefilled']:
                f['value'] = hint['value']
            f['linked_photos']=linked[field['id']]
            f['proposed_photos']=proposed[field['id']]
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
    from .access import role_for
    if role_for(request.user)==Profile.Roles.ENGINEER:
        from .category_intake import access as capture_access
        capture_access(request,checklist_id)
        return redirect('photo_workspace',checklist_id=checklist_id)
    access = survey_access(request, checklist_id)
    checklist = access['checklist']
    from .access import role_for
    actual_role=role_for(request.user)
    from .review_route_service import route_context
    routing=route_context(request.user,checklist)
    from .quality_workflow import quality_is_current
    quality_ready=quality_is_current(checklist) if checklist.governance_mode!='independent' else False
    from .access import users_for_project
    quality_candidates=users_for_project(checklist.project_id,{Profile.Roles.QUALITY_ENGINEER})
    can_assign_quality=actual_role in {Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD} and checklist.governance_mode!='independent' and checklist.status in {Checklist.Status.DRAFT,Checklist.Status.REJECTED,Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL}
    return render(request, 'dashboards/custom_checklist.html', {'review_route':routing,'checklist': checklist, 'sections': survey_context(checklist, request), 'schema': checklist.schema_snapshot, 'can_edit': access.get('can_edit') and checklist.status != Checklist.Status.FINAL, 'can_assign_quality':can_assign_quality,'quality_reviewer_candidates':quality_candidates,'can_quality_review': checklist.governance_mode!='independent' and actual_role==Profile.Roles.QUALITY_ENGINEER and checklist.quality_reviewer_id==request.user.pk and checklist.status in {Checklist.Status.SUBMITTED,Checklist.Status.REVIEW,Checklist.Status.PARTIAL} and not quality_ready, 'can_review': actual_role==Profile.Roles.TEAM_LEAD and checklist.governance_mode!='independent' and quality_ready, 'can_submit': actual_role==Profile.Roles.ENGINEER and checklist.user_id==request.user.pk and bool(access.get('can_edit')), 'can_manage_templates': is_template_admin(request), 'missing': missing_required(checklist), 'can_decide': checklist.status in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]})


@require_http_methods(['POST'])
def custom_save(request, checklist_id):
    try:
        survey_access(request, checklist_id, edit=True)
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or not isinstance(payload.get('answers'), dict):
            raise ValidationError('Provide an answers object.')
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            survey_access(request, checklist_id, edit=True)
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
            WorkAssignment.objects.filter(checklist=checklist, status=WorkAssignment.Status.PENDING).update(
                status=WorkAssignment.Status.IN_PROGRESS, started_at=timezone.now())
        return JsonResponse({'status': 'success', 'missing': missing_required(checklist), 'can_decide': checklist.status in [Checklist.Status.SUBMITTED, Checklist.Status.REVIEW, Checklist.Status.PARTIAL]})
    except (ValidationError, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid field value, missing N/A reason, or locked checklist.'}, status=400)


@require_http_methods(['POST'])
def custom_upload(request, checklist_id, field_id):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
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
            survey_access(request, checklist_id, edit=True)
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
    from .category_intake import projected_checklist
    checklist=projected_checklist(checklist)
    paths = (checklist.image_data or {}).get(field_id, [])
    if index >= len(paths) or not default_storage.exists(paths[index]):
        raise Http404()
    response = FileResponse(default_storage.open(paths[index], 'rb'), content_type='image/png')
    response['Cache-Control'] = 'private, no-store'
    return response


@require_http_methods(['POST'])
def custom_photo_delete(request, checklist_id, field_id, index):
    from .category_intake import deny_engineer_ai
    deny_engineer_ai(request,checklist_id)
    try:
        survey_access(request, checklist_id, edit=True)
        with transaction.atomic():
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            survey_access(request, checklist_id, edit=True)
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
    from django.urls import reverse
    # Keep the field workspace after a successful submission, but accept only
    # this record's server-generated relative path rather than an arbitrary URL.
    submitted_return = 'photo_workspace' if request.POST.get('return_to') == reverse('photo_workspace', args=[checklist_id]) else 'custom_checklist'
    try:
        access = survey_access(request, checklist_id)
        from .access import role_for
        if role_for(request.user)!=Profile.Roles.ENGINEER or request.user!=access['checklist'].user:
            return HttpResponse(status=403)
        from .independent_workflow import is_independent,submit_revision
        if is_independent(access['checklist']):
            submit_revision(request.user,access['checklist'])
            messages.success(request,'Frozen revision submitted for independent validation.')
            return redirect(submitted_return,checklist_id=checklist_id)
        survey_access(request,checklist_id,edit=True)
        with transaction.atomic():
            from .governance_views import lock_governance
            lock_governance(request.user)
            refreshed=survey_access(request,checklist_id)
            if role_for(request.user)!=Profile.Roles.ENGINEER or request.user!=refreshed['checklist'].user:
                return HttpResponse(status=403)
            survey_access(request,checklist_id,edit=True)
            checklist = Checklist.objects.select_for_update().get(pk=checklist_id)
            if checklist.status == Checklist.Status.FINAL:
                raise ValidationError('This approved checklist is locked.')
            missing = missing_required(checklist)
            if missing:
                raise ValidationError('Complete required fields: '+', '.join(missing))
            from .quality_workflow import require_quality_reviewer
            require_quality_reviewer(checklist.project_id,checklist.quality_reviewer,checklist.user_id)
            checklist.quality_approval={}
            checklist.status = Checklist.Status.PARTIAL if checklist.section_approvals else Checklist.Status.SUBMITTED
            checklist.save(update_fields=['status', 'quality_approval', 'updated_at'])
            WorkAssignment.objects.filter(checklist=checklist).update(submitted_at=timezone.now())
            from .workflow_service import sync_assignment
            sync_assignment(checklist)
            from .governance_views import audit
            audit(request.user, 'survey_submitted', checklist.project, checklist_id=checklist.pk)
        messages.success(request, 'Checklist submitted for review.')
        return redirect(submitted_return, checklist_id=checklist_id)
    except ValidationError as error:
        messages.error(request, '; '.join(error.messages))
    return redirect('custom_checklist', checklist_id=checklist_id)


@require_http_methods(['GET'])
def custom_download(request, checklist_id):
    checklist = survey_access(request, checklist_id)['checklist']
    from .category_intake import projected_checklist
    checklist=projected_checklist(checklist)
    content = export_custom_excel(checklist)
    response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    from django.utils.text import slugify
    filename = slugify(checklist.site_id) or f'survey-{checklist.id}'
    response['Content-Disposition'] = f'attachment; filename="{filename}-checklist.xlsx"'
    response['Cache-Control'] = 'private, no-store'
    return response
