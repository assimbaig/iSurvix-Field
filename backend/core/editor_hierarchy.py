"""Backward-compatible editor metadata over the existing section.group hierarchy."""
from copy import deepcopy
from django.core.exceptions import ValidationError


def group_names(definition):
    groups=list(definition.get('editor_groups', []))
    for section in definition.get('sections', []):
        name=section.get('group', '')
        if name and name not in groups:groups.append(name)
    return groups


def validate_metadata(definition):
    if 'editor_groups' in definition:
        groups=definition['editor_groups']
        if (not isinstance(groups,list) or len(groups)>100 or
            any(not isinstance(name,str) or not name.strip() or name!=name.strip() or len(name)>160 for name in groups) or
            len({name.casefold() for name in groups})!=len(groups)):
            raise ValidationError('Provide distinct group names of at most 160 characters, with at most 100 groups.')
        for section in definition.get('sections',[]):
            if isinstance(section,dict) and section.get('group','') and section['group'] not in groups:
                raise ValidationError('Each grouped section must belong to an existing group.')
    decisions=definition.get('editor_recommendation_decisions',{})
    from .template_service import IDENTIFIER
    if (not isinstance(decisions,dict) or len(decisions)>3000 or any(
        not isinstance(key,str) or not IDENTIFIER.fullmatch(key) or value not in ('accepted','dismissed')
        for key,value in decisions.items())):
        raise ValidationError('Invalid saved recommendation decisions.')


def merge_group_names(definition, additions):
    """Merge optional metadata when appending points, leaving old section IDs intact."""
    if 'editor_groups' not in definition and not any('editor_groups' in item for item in additions):
        return definition
    result=deepcopy(definition)
    names=group_names(result)
    for item in additions:
        for name in group_names(item):
            if name not in names:names.append(name)
    result['editor_groups']=names
    return result
