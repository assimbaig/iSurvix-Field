"""Display the saved review route without manufacturing approval decisions."""
from .workflow_service import workflow_stage


def workflow_steps(checklist):
    stage=workflow_stage(checklist)
    route=getattr(checklist,'review_route_record',None)
    policy=getattr(checklist,'review_policy',None)
    keys=['engineer','quality_engineer','team_lead']
    labels={'engineer':'Engineer','quality_engineer':'QA','team_lead':'Team Lead','project_manager':'Project Manager','client':'Client','closed':'Closed'}
    if not route and policy and policy.workflow_version==1:keys=['engineer','team_lead','project_manager']
    if route and route.layer_count==4 or not route and checklist.client_review_required is not False:
        keys.append('client')
        if not route and checklist.client_review_required is None:labels['client']='Client if required'
    keys.append('closed')
    current=keys.index(stage) if stage in keys else 0
    return [{'key':key,'label':labels[key],'state':'current' if index==current else 'complete' if index<current else 'pending',
             'description':'Current step' if index==current else 'Earlier step' if index<current else 'Upcoming step'} for index,key in enumerate(keys)]
