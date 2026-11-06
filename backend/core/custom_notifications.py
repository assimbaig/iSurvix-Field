"""Safe company customization; never a template-language or raw audit renderer."""
from collections import Counter
from datetime import datetime,timedelta,timezone as utc
from string import Formatter
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
import hashlib,json,uuid
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction,models
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from .access import company_id_for,is_super_admin,role_for
from .models import CompanyNotificationSettings,GovernanceAudit,Profile,WorkflowEmailDelivery

KINDS={'invitation':'Account invitation','assignment':'Task assignment','submission':'Submission','approval':'Approval','rejection':'Rejection',
       'client_review':'Client review','report_ready':'Draft report','report_released':'Released report',
       'company_update':'Company account or client change','project_update':'Project or access change','daily':'Project daily report','daily_combined':'Combined daily report'}
TOKENS={'recipient_name','company_name','project_name','site_id','event_title','event_time','status','task_url','default_body','summary'}
SUBJECT_LIMITS={'recipient_name':80,'company_name':160,'project_name':120,'site_id':120,'event_title':60,'event_time':35,'status':50}
PROJECT_ACTIONS={'project_created','project_client_assigned','project_administrator_assigned','project_membership_grant','project_membership_revoke','invitation_accepted','invitation_revoked','member_activate','member_deactivate','member_unlock','member_role','project_company_assigned'}
COMPANY_ACTIONS={'client_organization_created','admin_industry_bound','member_activate','member_deactivate','member_unlock','member_role','invitation_accepted','invitation_revoked'}

def guard(actor,company=None):
    if is_super_admin(actor):return
    profile=Profile.objects.select_related('admin_industry').filter(user=actor).first()
    if (not actor.is_active or role_for(actor)!=Profile.Roles.ADMIN or not profile or profile.admin_industry_pending
        or not profile.admin_industry_id or not profile.admin_industry.is_active or not company_id_for(actor)
        or company is not None and company_id_for(actor)!=company.pk):
        raise PermissionDenied('Notification settings require company administration access.')


def validate_templates(templates):
    if not isinstance(templates,dict) or set(templates)-set(KINDS):raise ValidationError('Choose supported notification types only.')
    result={}
    for kind,pair in templates.items():
        if not isinstance(pair,dict) or set(pair)!={'subject','body'}:raise ValidationError('Each template needs a subject and body.')
        for field,maximum in [('subject',180),('body',12000)]:
            text=pair[field]
            if not isinstance(text,str) or not text.strip() or len(text)>maximum:raise ValidationError('Template text is empty or too long.')
            if '<' in text or '>' in text or '\x00' in text or field=='subject' and ('\n' in text or '\r' in text):raise ValidationError('Use plain text; subject headers must remain on one line.')
            try:
                for _,name,format_spec,conversion in Formatter().parse(text):
                    if field=='subject' and name is not None and name not in SUBJECT_LIMITS:raise ValidationError('Subjects may use only short, single-line placeholders; body, summary and URL placeholders belong in the message.')
                    if name is not None and (name not in TOKENS or format_spec or conversion):raise ValidationError('Unknown or unsupported placeholder. Use only the displayed names.')
            except ValueError:raise ValidationError('A template placeholder has unmatched braces.') from None
        if len(pair['subject'].format_map({name:'X'*maximum for name,maximum in SUBJECT_LIMITS.items()}))>200:raise ValidationError('This subject can expand beyond 200 characters. Shorten it or use fewer placeholders.')
        if kind=='daily_combined' and not any(name in {'summary','default_body'} for _,name,_,_ in Formatter().parse(pair['body'])):raise ValidationError('A combined report template must include {summary} or {default_body} so notification totals are retained.')
        budget=0
        for literal,name,_,_ in Formatter().parse(pair['body']):
            budget+=len(literal.encode('utf-8'))
            if name:budget+=40000 if name in {'summary','default_body'} else 2048 if name=='task_url' else SUBJECT_LIMITS[name]*4
        if budget>60000:raise ValidationError('The expanded message can exceed the email size limit. Use the standard body or summary once and shorten added text.')
        result[kind]=dict(pair)
    return result


@transaction.atomic
def save_settings(actor,company,*,expected_version,templates,combined_daily_enabled,daily_time,timezone_name):
    guard(actor,company)
    templates=validate_templates(templates)
    try:ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError,ValueError,TypeError):raise ValidationError('Choose a valid IANA timezone.') from None
    if not hasattr(daily_time,'hour') or daily_time.second or daily_time.microsecond:raise ValidationError('Choose a business-day time in whole minutes.')
    if getattr(daily_time,'tzinfo',None) is not None:raise ValidationError('Choose a local business-day time.')
    if type(combined_daily_enabled) is not bool:raise ValidationError('Choose whether to send the combined report.')
    config=CompanyNotificationSettings.objects.select_for_update().filter(company=company).first()
    if type(expected_version) is not int or expected_version!=(config.version if config else 0):raise ValidationError('Settings changed. Reload the saved version before retrying.',code='conflict')
    previous={'version':config.version,'combined_daily_enabled':config.combined_daily_enabled,'daily_time':config.daily_time.isoformat(),'timezone_name':config.timezone_name,'template_kinds':sorted(config.templates)} if config else None
    if config is None:config=CompanyNotificationSettings(company=company,version=0)
    if combined_daily_enabled and (not config.combined_daily_enabled or not config.digest_started_at):
        config.digest_started_at=timezone.now();config.last_digest_day=None;config.last_digest_end=None
    config.version+=1;config.templates=templates;config.combined_daily_enabled=combined_daily_enabled
    config.daily_time=daily_time;config.timezone_name=timezone_name;config.updated_by=actor;config.full_clean();config.save()
    GovernanceAudit.objects.create(actor=actor,actor_name=actor.username,action='notification_settings.updated',details={'company_id':company.pk,'before':previous,'after':{'version':config.version,'combined_daily_enabled':config.combined_daily_enabled,'daily_time':config.daily_time.isoformat(),'timezone_name':config.timezone_name,'template_kinds':sorted(templates)},'templates_sha256':hashlib.sha256(json.dumps(templates,sort_keys=True).encode()).hexdigest()})
    return config


def custom_message(delivery,user,project,checklist,subject,body):
    from .invitation_email import _public_origin
    config=CompanyNotificationSettings.objects.filter(company_id=delivery.company_id).first()
    pair=config.templates.get(delivery.kind) if config and isinstance(config.templates,dict) else None
    if not pair:return subject,body
    validate_templates({delivery.kind:pair})
    safe=lambda value:' '.join(str(value).split())[:180]
    values={'recipient_name':safe(user.get_full_name() or user.username)[:80],'company_name':safe(config.company.name)[:160],
        'project_name':safe(project.name)[:120] if project else 'All authorized projects','site_id':safe(checklist.site_id or checklist.pk)[:120] if checklist else '',
        'event_title':KINDS.get(delivery.kind,'Notification'),'event_time':delivery.created_at.isoformat(),
        'status':safe(checklist.get_status_display()) if checklist else '',
        'task_url':_public_origin()+(reverse('custom_checklist',args=[checklist.pk]) if checklist else reverse('governance_home')),
        'default_body':body,'summary':body}
    rendered_subject=pair['subject'].format_map(values)
    if '\n' in rendered_subject or '\r' in rendered_subject or len(rendered_subject)>200:raise ValidationError('Invalid or overlong subject header.')
    rendered_body=pair['body'].format_map(values)
    final_body=rendered_body+'\n\nOpen iField (sign-in required): '+values['task_url']
    if len(final_body.encode('utf-8'))>65536:raise ValidationError('Expanded message exceeds the email limit. Shorten the custom template.')
    return rendered_subject,final_body


def business_window(config,day):
    zone=ZoneInfo(config.timezone_name)
    return (datetime.combine(day-timedelta(days=1),config.daily_time,tzinfo=zone),datetime.combine(day,config.daily_time,tzinfo=zone))


def delivery_window(delivery):
    parts=delivery.event_key.split('|')
    if len(parts)!=4 or parts[0]!=f'combined:{delivery.company_id}:{delivery.digest_day.isoformat()}':raise ValidationError('Combined report window is invalid.')
    start,end=map(datetime.fromisoformat,parts[1:3])
    if not start.tzinfo or not end.tzinfo or not start<end or end-start>timedelta(days=4):raise ValidationError('Combined report window is invalid.')
    return start,end,parts[3]


def authorized_events(user,company_id,start,end):
    from .workflow_email import _fresh
    from .models import InvitationEmailDelivery
    from .access import can_access_project
    jobs=WorkflowEmailDelivery.objects.filter(recipient=user,company_id=company_id,created_at__gte=start,created_at__lt=end).exclude(kind__in=['daily','daily_combined']).exclude(status='cancelled').select_related('project').annotate(_source_project_id=F('source_audit__project_id')).order_by('created_at','pk')
    permission_cache={}
    for job in jobs.iterator(chunk_size=100):
        # Visibility is stable for one rendered message; a fresh cache is built
        # again by the existing before-send recheck. Never load evidence JSON
        # once for every notification referring to the same task.
        if job.kind=='project_update' and job._source_project_id!=job.project_id:continue
        key=(job.project_id,job.company_id,job.expected_role,
             'assignment' if job.kind=='assignment' else 'project' if job.kind=='project_update' else 'company' if job.kind=='company_update' else 'checklist',
             (job.assignment_id or job.source_audit_id) if job.kind=='assignment' else None if job.kind=='project_update' else job.source_audit_id if job.kind=='company_update' else job.checklist_id)
        if key not in permission_cache:permission_cache[key]=_fresh(job) is not None
        if permission_cache[key]:yield job
    invitations=InvitationEmailDelivery.objects.filter(created_at__gte=start,created_at__lt=end).filter(
        models.Q(invitation__company_id=company_id)|models.Q(invitation__company__isnull=True,invitation__project__company_id=company_id)).filter(
        models.Q(invitation__accepted_by_id=user.pk)|models.Q(invitation__accepted_by__isnull=True,invitation__email__iexact=user.email,invitation__role=role_for(user))).exclude(status='cancelled').select_related('invitation__project')
    from types import SimpleNamespace
    for row in invitations.iterator(chunk_size=100):
        invite=row.invitation
        if invite.project_id and not can_access_project(user,invite.project_id):continue
        yield SimpleNamespace(kind='invitation',project=invite.project,status=row.status)


def combined_context(delivery):
    from .access import role_for
    config=CompanyNotificationSettings.objects.filter(company_id=delivery.company_id,combined_daily_enabled=True).first()
    user=User.objects.select_related('profile').filter(pk=delivery.recipient_id,is_active=True).first()
    if not config or not user or company_id_for(user)!=delivery.company_id or role_for(user)!=delivery.expected_role or delivery.digest_day is None:return None
    start,end,_=delivery_window(delivery)
    if not next(authorized_events(user,delivery.company_id,start,end),None):return None
    return user,None,None


def queue_combined(now):
    # Limit work per tick; the saved cursor resumes the remaining days. Each
    # business day and its outbox rows commit together, including empty days.
    count=0
    ids=CompanyNotificationSettings.objects.filter(combined_daily_enabled=True).values_list('pk',flat=True)
    for config_id in ids.iterator(chunk_size=50):
        for _ in range(3):
            with transaction.atomic():
                config=CompanyNotificationSettings.objects.select_for_update().select_related('company').get(pk=config_id)
                if not config.combined_daily_enabled:break
                local=now.astimezone(ZoneInfo(config.timezone_name))
                completed=local.date() if local.time().replace(tzinfo=None)>=config.daily_time else local.date()-timedelta(days=1)
                activation=(config.digest_started_at or config.updated_at).astimezone(ZoneInfo(config.timezone_name)).date()
                day=config.last_digest_day+timedelta(days=1) if config.last_digest_day else activation
                if day>completed:break
                _,end=business_window(config,day)
                # A schedule edit changes the next end, never the UTC boundary
                # already covered by the prior day (including an empty day).
                # If an extreme offset change moves an end backwards, advance
                # only its date cursor until there is a positive UTC interval.
                if config.last_digest_end is None or end>config.last_digest_end:
                    count+=_queue_combined_day(config,day)
                    config.last_digest_end=end.astimezone(utc.utc)
                config.last_digest_day=day
                config.save(update_fields=['last_digest_day','last_digest_end'])
    return count


def _queue_combined_day(config,day):
    from .workflow_email import _audit
    from .models import InvitationEmailDelivery
    start,end=business_window(config,day)
    if config.last_digest_end is not None:start=config.last_digest_end
    recipients=set(WorkflowEmailDelivery.objects.filter(company_id=config.company_id,created_at__gte=start,created_at__lt=end).exclude(kind__in=['daily','daily_combined']).exclude(status='cancelled').values_list('recipient_id',flat=True))
    invite_emails=InvitationEmailDelivery.objects.filter(models.Q(invitation__company_id=config.company_id)|models.Q(invitation__company__isnull=True,invitation__project__company_id=config.company_id),created_at__gte=start,created_at__lt=end).exclude(status='cancelled').values_list('invitation__email',flat=True)
    for email in invite_emails:recipients.update(User.objects.filter(email__iexact=email).values_list('pk',flat=True))
    count=0
    for user in User.objects.filter(pk__in=recipients,is_active=True).select_related('profile'):
        if company_id_for(user)!=config.company_id or not next(authorized_events(user,config.company_id,start,end),None):continue
        key=f'combined:{config.company_id}:{day.isoformat()}'
        window_key=key+'|'+start.isoformat()+'|'+end.isoformat()+'|'+config.timezone_name
        delivery,created=WorkflowEmailDelivery.objects.get_or_create(dedupe_key=hashlib.sha256(f'{key}:{user.pk}'.encode()).hexdigest(),defaults={'event_key':window_key,'kind':'daily_combined','company':config.company,'recipient':user,'expected_role':role_for(user),'digest_day':day})
        if created:_audit(delivery,'queued');count+=1
    return count


def combined_message(delivery,user):
    from .workflow_email import _compact
    from .invitation_email import _public_origin
    config=CompanyNotificationSettings.objects.get(company_id=delivery.company_id,combined_daily_enabled=True)
    start,end,report_timezone=delivery_window(delivery)
    groups=Counter();totals=Counter();total=0
    labels={'accepted':'Accepted by mail server','failed':'Failed','uncertain':'Outcome uncertain','queued':'Queued','sending':'Processing'}
    for job in authorized_events(user,delivery.company_id,start,end):
        totals[(KINDS.get(job.kind,job.kind),labels.get(job.status,job.status))]+=1
        groups[(_compact(job.project.name) if job.project else 'Company account access',KINDS.get(job.kind,job.kind),labels.get(job.status,job.status))]+=1;total+=1
    body=[f'Combined iField notification report — {delivery.digest_day.isoformat()} ({report_timezone}).',f'Company: {_compact(config.company.name)}',f'Business-day window: {start.isoformat()} to {end.isoformat()}.',f'Authorized notification events: {total}.','', 'Project | Action | Email status | Count']
    body+=['All-event totals by action and mail status:']
    body.extend(f'{kind} | {status} | {number}' for (kind,status),number in sorted(totals.items()))
    body+=['','Project detail groups:']
    shown=0
    for (project,kind,status),number in sorted(groups.items()):
        line=f'{project} | {kind} | {status} | {number}'
        if len(('\n'.join(body+[line])).encode('utf-8'))>37000:break
        body.append(line);shown+=1
    if shown<len(groups):body.append(f'Message size limit: showing {shown} of {len(groups)} project groups. All {total} authorized events are included in the totals above; sign in for permitted task details.')
    body+=['','Accepted by mail server is not proof of inbox delivery.','Revoked or no-longer-visible records are excluded.','Open your authorized work: '+_public_origin()+reverse('governance_home')]
    return 'Combined daily iField report — '+delivery.digest_day.isoformat(),'\n'.join(body)


def custom_invitation_message(delivery,invitation,subject,body,link):
    from types import SimpleNamespace
    company_id=invitation.company_id or (invitation.project.company_id if invitation.project_id else None)
    if not company_id:return subject,body
    proxy=SimpleNamespace(kind='invitation',company_id=company_id,created_at=delivery.created_at)
    recipient=SimpleNamespace(username='Invited user',get_full_name=lambda:'')
    subject,body=custom_message(proxy,recipient,invitation.project if invitation.project_id else None,None,subject,body)
    # The token never enters configuration, digest events or audits. Always keep
    # the actual currently validated invitation URL in its private email only.
    return subject,body if link in body else body+'\n\nPrivate single-use invitation: '+link


def company_event_company(audit):
    from .models import ClientOrganization,ProjectInvitation
    details=audit.details if isinstance(audit.details,dict) else {}
    valid=lambda value:type(value) is int and 0<value<=9223372036854775807
    if audit.action=='client_organization_created':
        if not valid(details.get('client_organization_id')) or not valid(details.get('company_id')):return None
        return ClientOrganization.objects.filter(pk=details.get('client_organization_id'),company_id=details.get('company_id')).values_list('company_id',flat=True).first()
    if audit.action in {'invitation_accepted','invitation_revoked'}:
        if not valid(details.get('invitation_id')):return None
        return ProjectInvitation.objects.filter(pk=details.get('invitation_id')).values_list('company_id',flat=True).first()
    target=details.get('administrator_id') or details.get('user_id')
    profile=Profile.objects.select_related('project').filter(user_id=target).first() if valid(target) else None
    return profile.company_id or (profile.project.company_id if profile.project_id else None) if profile else None


def company_event_context(delivery):
    audit=GovernanceAudit.objects.filter(pk=delivery.source_audit_id,project__isnull=True,action__in=COMPANY_ACTIONS).first()
    user=User.objects.select_related('profile').filter(pk=delivery.recipient_id,is_active=True).first()
    if not audit or not user or company_id_for(user)!=delivery.company_id or company_event_company(audit)!=delivery.company_id or role_for(user)!=delivery.expected_role:return None
    if role_for(user) not in OPERATIONAL_ACCOUNT_ROLES:return None
    target=audit.details.get('administrator_id') or audit.details.get('user_id')
    if role_for(user)!=Profile.Roles.ADMIN and target!=user.pk:return None
    return user,None,None


OPERATIONAL_ACCOUNT_ROLES={Profile.Roles.ADMIN,Profile.Roles.TEAM_LEAD,Profile.Roles.QUALITY_ENGINEER,Profile.Roles.ENGINEER,Profile.Roles.CLIENT}


@transaction.atomic
def queue_company_event(audit):
    from .workflow_email import _audit
    company_id=company_event_company(audit)
    if not company_id:return 0
    targets=set(Profile.objects.filter(models.Q(company_id=company_id)|models.Q(company__isnull=True,project__company_id=company_id),role=Profile.Roles.ADMIN).values_list('user_id',flat=True))
    target=audit.details.get('administrator_id') or audit.details.get('user_id')
    if type(target) is int:targets.add(target)
    count=0
    for user in User.objects.filter(pk__in=targets,is_active=True).select_related('profile'):
        proxy=type('CompanyEventProbe',(),{'source_audit_id':audit.pk,'recipient_id':user.pk,'company_id':company_id,'expected_role':role_for(user)})()
        if company_event_context(proxy) is None:continue
        key=f'audit:{audit.pk}'
        delivery,created=WorkflowEmailDelivery.objects.get_or_create(dedupe_key=hashlib.sha256(f'{key}:{user.pk}'.encode()).hexdigest(),defaults={'event_key':key,'kind':'company_update','company_id':company_id,'recipient':user,'expected_role':role_for(user),'source_audit':audit})
        if created:_audit(delivery,'queued');count+=1
    return count
