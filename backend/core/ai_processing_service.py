"""Versioned company AI policy and durable, quota-accounted request execution."""
from copy import deepcopy
from datetime import timedelta
import hashlib,json,uuid
from urllib.error import URLError
from django.conf import settings
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from .access import company_id_for,is_super_admin,role_for
from .models import Profile,GovernanceAudit
from .ai_processing_models import AIProcessingSettings,AIProcessingPolicy,AIProcessingRequest,AIProcessingQuota,AIProcessingAttempt
from .ai_providers import endpoint_fingerprint,provider_for

FIELDS=('enabled','primary_provider','local_model','api_model','api_endpoint','allow_external_evidence','fallback_enabled','daily_request_limit','request_timeout')


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def serialize_settings(config):
    return {**{name:getattr(config,name) for name in FIELDS},'version':config.version if config.pk else 0}


def _authorise(actor,company):
    if is_super_admin(actor):return
    principal=Profile.objects.filter(user_id=actor.pk).first() if getattr(actor,'is_authenticated',False) else None
    if role_for(actor)!=Profile.Roles.ADMIN or company_id_for(actor)!=company.pk or not principal or principal.admin_industry_pending or not principal.admin_industry_id or not principal.admin_industry.is_active:
        raise PermissionDenied('Only the current company administrator can change AI settings.')


def update_settings(actor,company,payload,expected_version):
    _authorise(actor,company)
    if not isinstance(payload,dict) or set(payload)-set(FIELDS):raise ValidationError('Unsupported AI settings fields; credentials must stay with the platform operator.')
    with transaction.atomic():
        # Company row serializes initial creation as well as normal version updates.
        from .models import Company
        Company.objects.select_for_update().get(pk=company.pk)
        config=AIProcessingSettings.objects.select_for_update().filter(company=company).first()
        if expected_version!=(config.version if config else 0):raise ValidationError('AI settings changed. Reload before saving.',code='conflict')
        config=config or AIProcessingSettings(company=company,version=0)
        for name,value in payload.items():
            if name in ('enabled','allow_external_evidence','fallback_enabled') and type(value) is not bool:raise ValidationError('Use valid boolean AI settings.')
            if name in ('daily_request_limit','request_timeout') and type(value) is not int:raise ValidationError('Use whole numbers for AI limits.')
            if name not in ('enabled','allow_external_evidence','fallback_enabled','daily_request_limit','request_timeout') and not isinstance(value,str):raise ValidationError('Use text for AI model settings.')
            setattr(config,name,value)
        if not 0<=config.daily_request_limit<=1_000_000 or not 5<=config.request_timeout<=600:raise ValidationError('AI limits are outside their supported bounds.')
        if not config.local_model.strip() or any(t in config.local_model.lower() for t in (':cloud','-cloud')):raise ValidationError('Select an installed local model.')
        external=config.primary_provider=='https_ollama' or config.fallback_enabled
        if external:
            if not config.allow_external_evidence:raise ValidationError('Explicit external evidence permission is required for API processing or fallback.')
            if not config.api_model.strip():raise ValidationError('Select an API vision model.')
            endpoint_fingerprint(config.api_endpoint)
        config.updated_by=actor
        config.full_clean()
        config.version+=1;config.save()
        GovernanceAudit.objects.create(action='ai_settings_updated',actor=actor,actor_name=actor.username,details={'company_id':company.pk,'version':config.version,'changed_fields':sorted(payload),'enabled':config.enabled,'primary_provider':config.primary_provider})
        return config


def configured(job):
    if AIProcessingPolicy.objects.filter(job=job).exists():return True
    return AIProcessingSettings.objects.filter(company_id=job.revision.checklist.project.company_id,enabled=True).exists()


def policy_for(job):
    company_id=job.revision.checklist.project.company_id
    with transaction.atomic():
        from .models import Company
        Company.objects.select_for_update().get(pk=company_id)
        saved=AIProcessingPolicy.objects.filter(job=job).first()
        if saved:
            if saved.company_id!=company_id or _digest(saved.snapshot)!=saved.fingerprint:raise ValidationError('The saved AI policy failed integrity verification.')
            return saved
        config=AIProcessingSettings.objects.filter(company_id=company_id,enabled=True).first()
        if not config:raise ValidationError('No active company AI policy is configured.')
        data=serialize_settings(config)
        if data['primary_provider']=='https_ollama' or data['fallback_enabled']:
            data['endpoint_fingerprint']=endpoint_fingerprint(data['api_endpoint'])
        return AIProcessingPolicy.objects.create(job=job,company_id=company_id,snapshot=data,fingerprint=_digest(data))


def processing_identity(job):
    policy=policy_for(job)
    return {'version':'company-provider-policy-v1','model':job.model,'fingerprint':policy.fingerprint,'legacy_fingerprint':policy.fingerprint,'policy_version':policy.snapshot['version']}


def pin_processing_identity(job,identity):
    from .survey_processing import progress
    from .survey_processing_models import SurveyProcessingEvent
    if job.model_digest and job.model_digest!=identity['fingerprint']:
        raise ValidationError('This job already has another model or provider policy. Preserve its revision; submit changed inputs as a new revision.')
    if not job.model_digest:
        with transaction.atomic():
            progress(job,model_digest=identity['fingerprint'])
            SurveyProcessingEvent.objects.create(revision=job.revision,actor_id=job.revision.submitted_by_id,
                action='provider_policy_pinned',payload={**identity,'proof':'immutable_company_policy_snapshot'})


def lease_seconds(job):
    saved=AIProcessingPolicy.objects.filter(job=job).first()
    config=None if saved else AIProcessingSettings.objects.filter(company_id=job.revision.checklist.project.company_id,enabled=True).first()
    timeout=saved.snapshot['request_timeout'] if saved else config.request_timeout if config else 0
    return max(300,timeout*8+120) if timeout else max(300,getattr(settings,'OLLAMA_TIMEOUT',180)+120)


def _error_code(error):
    if isinstance(error,ValidationError) and getattr(error,'code','')=='local_unavailable':return 'local_worker_required'
    if isinstance(error,(TimeoutError,URLError,ConnectionError,OSError)):return 'provider_unavailable'
    return 'invalid_response'


def execute_request(job,key,context,callback):
    """callback receives a Provider; only strictly validated callback results are stored.

    Each source/mapping attempt consumes one daily unit, including failures and
    fallback. Vision metadata requests are part of that bounded inference unit.
    A crash may repeat an external request; a stale lease can never publish it.
    """
    if not isinstance(key,str) or not key or len(key)>300:raise ValidationError('The AI source identity is invalid.')
    policy=policy_for(job);snapshot=policy.snapshot
    signature=_digest({'context':context,'policy':policy.fingerprint})
    token=uuid.uuid4().hex
    with transaction.atomic():
        AIProcessingPolicy.objects.select_for_update().get(pk=policy.pk)
        request,_=AIProcessingRequest.objects.get_or_create(policy=policy,key=key,defaults={'input_digest':signature})
        if request.input_digest!=signature:raise ValidationError('AI inputs changed within this submission. Preserve it and create a new revision.')
        if request.state=='succeeded':
            if _digest(request.result)!=request.result_digest:raise ValidationError('The saved AI result failed integrity verification.')
            return deepcopy(request.result)
        if request.state=='running' and request.lease_until and request.lease_until>timezone.now():raise ValidationError('This AI source is already processing. Retry after the active attempt finishes.')
        if request.attempts>=4:raise ValidationError('This source reached its bounded retry limit. Completed results are preserved.')
        AIProcessingAttempt.objects.filter(request=request,outcome='running').update(outcome='abandoned',error_code='worker_interrupted',finished_at=timezone.now())
        request.state='running';request.lease_token=token;request.lease_until=timezone.now()+timedelta(seconds=lease_seconds(job));request.error_code=''
        request.save()
    providers=[snapshot['primary_provider']]
    if snapshot['fallback_enabled']:providers.append('https_ollama' if providers[0]=='local' else 'local')
    for kind in providers:
        receipt=None
        try:
            with transaction.atomic():
                current=AIProcessingRequest.objects.select_for_update().get(pk=request.pk)
                if current.lease_token!=token:raise ValidationError('This processing lease was replaced; no stale output was saved.')
                from .models import Company
                Company.objects.select_for_update().get(pk=policy.company_id)
                quota,_=AIProcessingQuota.objects.get_or_create(company_id=policy.company_id,day=timezone.now().date())
                if quota.used>=snapshot['daily_request_limit']:raise ValidationError('The company AI daily quota is exhausted. Completed results are preserved.')
                if current.attempts>=4:raise ValidationError('This AI request reached its bounded retry limit.')
                quota.used+=1;quota.save(update_fields=['used'])
                current.attempts+=1;current.save(update_fields=['attempts','updated_at'])
                receipt=AIProcessingAttempt.objects.create(request=current,number=current.attempts,provider=kind,model=snapshot['local_model'] if kind=='local' else snapshot['api_model'])
            try:
                result=callback(provider_for(kind,snapshot))
                if not isinstance(result,dict):raise ValidationError('AI output was not a structured result.')
                signature_result=_digest(result)
            except Exception as error:
                code=_error_code(error)
                AIProcessingAttempt.objects.filter(pk=receipt.pk).update(outcome='failed',error_code=code,finished_at=timezone.now())
                # Record only controlled error codes, never endpoint exceptions/payloads.
                if kind==providers[-1]:raise ValidationError('AI provider failed ('+code+'). Saved evidence is preserved; retry processing.') from None
                continue
            with transaction.atomic():
                current=AIProcessingRequest.objects.select_for_update().get(pk=request.pk)
                if current.lease_token!=token or not current.lease_until or current.lease_until<=timezone.now():raise ValidationError('The processing lease expired. No stale output was saved.')
                current.state='succeeded';current.result=result;current.result_digest=signature_result;current.lease_token='';current.lease_until=None
                current.save()
                AIProcessingAttempt.objects.filter(pk=receipt.pk).update(outcome='succeeded',finished_at=timezone.now())
            return deepcopy(result)
        except Exception:
            if receipt:
                AIProcessingAttempt.objects.filter(pk=receipt.pk,outcome='running').update(outcome='abandoned',error_code='lease_or_processing_interrupted',finished_at=timezone.now())
            AIProcessingRequest.objects.filter(pk=request.pk,lease_token=token).update(state='failed',error_code='processing_failed',lease_token='',lease_until=None)
            raise


def execute_source(job,source,compact=False):
    from .survey_evidence import analyse_source
    def call(provider):
        if provider.kind=='local':
            from .photo_queue import photo_inference_lease
            with photo_inference_lease() as check:
                result=analyse_source(source,provider.model,compact=compact,transport=provider.request,verify=provider.verify)
                check()
                return result
        return analyse_source(source,provider.model,compact=compact,transport=provider.request,verify=provider.verify)
    return execute_request(job,source['source_id'],source,call)


def execute_mapping(job,batch):
    from .survey_checklist_mapping import bind_batch,binding_identity
    def call(provider):
        provider.verify(provider.model)
        if provider.kind=='local':
            from .photo_queue import photo_inference_lease
            with photo_inference_lease() as check:
                result=bind_batch(batch,provider.model,transport=provider.request)
                check()
        else:result=bind_batch(batch,provider.model,transport=provider.request)
        # The enclosing job's immutable binding context is independent of the
        # particular fallback model; actual model is retained in attempt receipts.
        result['identity']=binding_identity(batch,job.model)
        return result
    return execute_request(job,batch['key'],batch,call)
