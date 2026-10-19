"""Atomic editable industry identities with a stable technical workflow family."""
import hashlib
import hmac
import json
import re
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,IntegrityError
from .models import IndustryCatalog,Project
from .access import is_super_admin

FAMILIES={'telecom','construction','other'}

def industry_token(instance):
    return hashlib.sha256(json.dumps([instance.pk,instance.code,instance.name,instance.description,instance.workflow_family,instance.is_active],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def industry_family(value):
    """Resolve stable technical family from a catalog record, Project or code."""
    if isinstance(value,IndustryCatalog):return value.workflow_family
    code=value.industry if isinstance(value,Project) else value
    if not isinstance(code,str):return 'other'
    return IndustryCatalog.objects.filter(code=code).values_list('workflow_family',flat=True).first() or 'other'

family_for_code=industry_family
project_workflow_family=industry_family

@transaction.atomic
def update_industry(actor,instance,code,name,description='',is_active=True,expected_token=None,workflow_family=None):
    from .governance_views import lock_governance,audit
    lock_governance(actor);actor=User.objects.get(pk=actor.pk)
    if not is_super_admin(actor):raise PermissionDenied('Only Super Admin may manage industries.')
    item=IndustryCatalog.objects.select_for_update().get(pk=instance.pk) if instance and instance.pk else IndustryCatalog()
    editing=bool(item.pk)
    if editing and (not isinstance(expected_token,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_token) or not hmac.compare_digest(expected_token,industry_token(item))):raise ValidationError('This industry changed. Reload before saving.')
    family=item.workflow_family if editing else workflow_family or (instance.workflow_family if instance else 'other')
    if editing and workflow_family is not None and workflow_family!=family:raise ValidationError('The existing workflow family is fixed.')
    if family not in FAMILIES:raise ValidationError('Choose a supported workflow family.')
    if not isinstance(code,str) or not code or len(code)>20 or not isinstance(name,str) or not name.strip() or len(name)>100:raise ValidationError('Provide a short industry code and name.')
    if not isinstance(description,str) or len(description)>6000:raise ValidationError('Description must be at most 6000 characters.')
    if type(is_active) is not bool:raise ValidationError('Active must be true or false.')
    old_code=item.code
    previous={key:getattr(item,key) for key in ['code','name','description','is_active']} if editing else None
    affected_project_ids=list(Project.objects.filter(industry=old_code).values_list('pk',flat=True)) if editing and old_code!=code else []
    item.code=code;item.name=name;item.description=description;item.is_active=is_active;item.workflow_family=family
    item.full_clean()
    # Case-insensitive collisions remain confusing even when SQLite treats them distinct.
    if IndustryCatalog.objects.exclude(pk=item.pk).filter(code__iexact=item.code).exists() or IndustryCatalog.objects.exclude(pk=item.pk).filter(name__iexact=item.name).exists():raise ValidationError('Industry code and name must be unique, ignoring case.')
    item._allow_code_rename=True
    try:
        item.save()
        projects=Project.objects.filter(industry=old_code).update(industry=item.code) if editing and old_code!=item.code else 0
    finally:item._allow_code_rename=False
    audit(actor,'industry_updated' if editing else 'industry_created',industry_id=item.pk,old_code=old_code if editing else None,code=item.code,name=item.name,workflow_family=item.workflow_family,is_active=item.is_active,renamed_project_count=projects,affected_project_ids=affected_project_ids,previous=previous)
    return item

def create_industry(actor,code,name,description='',is_active=True,workflow_family='other'):
    return update_industry(actor,None,code,name,description,is_active,workflow_family=workflow_family)
