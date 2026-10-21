"""Read-only saved workflow indicator for operational site rows."""
from django import template
from core.task_presentation import workflow_steps
register=template.Library()

@register.inclusion_tag('dashboards/_task_workflow_steps.html')
def task_workflow_steps(checklist):
    return {'steps':workflow_steps(checklist)}
