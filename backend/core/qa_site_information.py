"""One QA site table projected from frozen sources and existing review answers.

There is deliberately no second editing store: editable cells refer to stable
fields from the submitted checklist and save through its append-only QA action.
"""
from copy import deepcopy

from .template_views import field_is_locked


def table(c,information,items,*,can_review):
    by_id={item['id']:item for item in items}
    rows=[]
    sources=[{**row,'scope':'context'} for row in information.get('context',[])]+information.get('fields',[])
    for source in sources:
        scope=source.get('scope','context')
        item=by_id.get(source['id']) if scope=='general' else None
        stable=source['id'] if item is not None else None
        locked=bool(stable and field_is_locked(c,stable))
        identity=bool(source.get('system'))
        confirm=bool(stable and can_review and not locked)
        editable=confirm and not identity
        if not stable:
            read_only='Submitted system/site source; return to Engineer to correct. No editable approved checklist field is configured for this cell.'
        elif locked:
            read_only='This checklist section is approved and locked.'
        elif not can_review:
            read_only='This QA review is read-only at its current workflow stage.'
        elif identity:
            read_only='System identity cannot be edited. Confirm the submitted value without changing it.'
        else:
            read_only=''
        submitted=deepcopy(source.get('value'))
        value=deepcopy(item.get('value')) if item is not None else deepcopy(submitted)
        rows.append({'id':source['id'],'key':scope+':'+source['id'],'scope':scope,
            'label':source['label'],'field_id':stable,'section_id':source.get('section_id',''),
            'type':source.get('type','text'),'value':value,'submitted_value':submitted,
            'can_edit':editable,'can_confirm':confirm,'read_only_reason':read_only,
            'status':item.get('status','Missing') if item else 'Submitted source',
            'accepted':bool(item and item.get('accepted')),
            'sources':deepcopy(item.get('sources',[])) if item else [],
            'reason':item.get('reason','') if item else '',
            'reviewed_by':item.get('qa_value_by',item.get('qa_by')) if item else None,
            'options':deepcopy(source.get('options',[])),'unit':source.get('unit',''),
            'required':bool(source.get('required')),'system':source.get('system',''),
            'source':source.get('source','frozen_submission'),'source_note':source.get('source_note',''),
            'group_label':{'context':'System record','site':'Submitted site data','general':'Approved checklist'}[scope]})
    return {'rows':rows,'can_review':bool(can_review),
        'notice':'QA corrections are saved as reviewed checklist answers. The submitted Engineer record stays unchanged.'}
