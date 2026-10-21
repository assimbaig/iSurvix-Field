"""Explicit, scoped template lifecycle. Saved survey snapshots are never rewritten."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from .models import ChecklistTemplate


def require_editable(actor, template):
    from .template_views import template_scope
    from .access import managed_project_ids
    if not template_scope(actor).filter(pk=template.pk).exists():
        raise PermissionDenied('This checklist is outside your project scope.')
    projects=managed_project_ids(actor)
    if template.projects.exclude(pk__in=projects).exists() or template.checklists.exclude(project_id__in=projects).exists():
        raise PermissionDenied('Replicate this shared source into your own draft.')
    if template.published or template.disabled or template.checklists.exists():
        raise ValidationError('Only enabled, unpublished, unused drafts can be edited. Unpublish an unused version or replicate a used checklist.')


def lifecycle(actor, template_id, action, expected):
    from .checklist_wizard_service import guard
    from .template_views import template_scope, template_edit_digest
    from .governance_views import lock_governance, audit
    with transaction.atomic():
        lock_governance(actor); guard(actor, True)
        template = template_scope(actor).filter(pk=template_id).first()
        if not template:
            raise PermissionDenied('This checklist is outside your project scope.')
        template = ChecklistTemplate.objects.select_for_update().get(pk=template.pk)
        if expected != template_edit_digest(template):
            raise ValidationError('This checklist changed in another window. Refresh the table and try again.')
        # A source shared with a project outside the Admin scope must be copied.
        from .access import managed_project_ids
        projects = managed_project_ids(actor)
        if template.projects.exclude(pk__in=projects).exists() or template.checklists.exclude(project_id__in=projects).exists():
            raise PermissionDenied('Replicate this shared source before making changes.')
        used = template.checklists.exists()
        if action in {'unpublish', 'delete'} and used:
            raise ValidationError('This checklist is in use. Its structure and history are protected; disable or replicate it.')
        if action == 'unpublish':
            template.published = False
            template.save(update_fields=['published'])
        elif action in {'disable', 'enable'}:
            template.disabled = action == 'disable'
            template.save(update_fields=['disabled'])
        elif action == 'delete':
            if template.published:
                raise ValidationError('Unpublish this unused checklist before deleting it.')
            if template.projects.exists():
                raise ValidationError('Remove this checklist from project defaults before deleting it.')
            try:
                template.delete()
            except ProtectedError as error:
                raise ValidationError('Historical references protect this checklist. Disable it instead.') from error
        else:
            raise ValidationError('Choose an available checklist action.')
        audit(actor, 'checklist_' + action, template_id=template_id)


def table_rows(actor):
    from .template_views import template_scope, template_edit_digest
    from .access import managed_project_ids
    projects = set(managed_project_ids(actor))
    rows = []
    for template in template_scope(actor).prefetch_related('projects', 'checklists').order_by('-created_at'):
        work = list(template.checklists.all())
        shared = any(p.pk not in projects for p in template.projects.all()) or any(c.project_id not in projects for c in work)
        can_manage = not shared
        rows.append({'id':template.pk,'name':template.name,'version':template.version,
            'published':template.published,'disabled':template.disabled,'owned':template.created_by_id==actor.pk,
            'state':'Disabled' if template.disabled else 'Published' if template.published else 'Draft',
            'in_use':bool(work),'work_count':len(work),'project_count':len(template.projects.all()),
            'sections':len(template.definition.get('sections',[])),
            'points':sum(len(s.get('fields',[])) for s in template.definition.get('sections',[])),
            'token':template_edit_digest(template),'can_manage':can_manage,
            'can_edit':can_manage and not work and not template.published and not template.disabled,
            'can_unpublish':can_manage and not work and template.published,
            'can_delete':can_manage and not work and not template.published and not template.projects.all()})
    return rows
