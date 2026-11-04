"""Read-only saved workflow indicator for operational site rows."""
from django import template
from core.task_presentation import workflow_steps
register=template.Library()

@register.inclusion_tag('dashboards/_task_workflow_steps.html')
def task_workflow_steps(checklist):
    return {'steps':workflow_steps(checklist,stage=getattr(checklist,'display_workflow_stage',None))}


@register.simple_tag
def task_display_label(checklist,fallback=''):
    if not checklist:return fallback
    # Python's short circuit avoids eager Django default-filter arguments.
    return getattr(checklist,'display_workflow_label',None) or checklist.workflow_label or fallback


@register.simple_tag
def task_display_stage(checklist):
    loaded=getattr(checklist,'display_workflow_stage',None)
    return loaded if loaded is not None else checklist.workflow_stage


@register.simple_tag
def task_display_version(checklist):
    if hasattr(checklist,'display_workflow_version'):return checklist.display_workflow_version
    policy=getattr(checklist,'review_policy',None)
    return policy.workflow_version if policy else None
