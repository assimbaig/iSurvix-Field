"""Trusted offline update catalog, owner requests and a signed root-local bridge.

The web application neither invokes Docker nor executes packages. Requests wait
for an explicit operator/installed host worker. Host receipt directories must be
mounted read-only; their journal lives outside application rollback databases.
"""
import hashlib,hmac,json,os,re,time,uuid
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import IntegrityError,transaction
from .access import is_super_admin
from .models import GovernanceAudit
from .operations_service import release_id
from .update_models import ServerUpdateRequest,ServerUpdateEvent

SHA40=re.compile(r'[a-f0-9]{40}')
SHA64=re.compile(r'[a-f0-9]{64}')
ACTIVE={'pending','verified','applying'}
RECOVERY_REQUIRED={'activation_uncertain','recovery_required','interrupted','migration_failed','health_failed'}
ERRORS={'','package_invalid','source_mismatch','catalog_changed','authority_revoked','backup_failed',
        'migration_failed','health_failed','interrupted','unsupported_version','artifact_unavailable',
        'operation_failed','recovery_required','cancelled','activation_uncertain'}
TRANSITIONS={'pending':{'verified','failed'},'verified':{'verified','applying','failed'},
             'applying':{'applying','completed','failed','rolled_back'},'failed':{'rolled_back'},
             'completed':set(),'rolled_back':set()}
ERROR_LABELS={'package_invalid':'Package validation failed.','source_mismatch':'The installed release changed.',
    'catalog_changed':'The trusted update catalog changed.','authority_revoked':'The requesting owner no longer has access.',
    'backup_failed':'The backup did not complete.','migration_failed':'The candidate migration did not complete.',
    'health_failed':'Candidate health checks failed.','interrupted':'The host operation was interrupted; operator recovery is required.',
    'unsupported_version':'This source version is unsupported.','artifact_unavailable':'The approved artifact is unavailable.',
    'operation_failed':'The host operation stopped. Review private operator logs.',
    'recovery_required':'Operator recovery is required before another attempt.','cancelled':'The request was cancelled.',
    'activation_uncertain':'Activation could not be confirmed. Preserve both runtimes and consult the host operator.'}


def owner(actor):
    if not is_super_admin(actor):raise PermissionDenied('Only the current platform owner can manage server updates.')


def _setting(name,default=''):
    return getattr(settings,name,os.environ.get(name,default))


def canonical(payload):
    return json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def sign_payload(domain,payload):
    if domain not in ('request-v1','receipt-v1'):raise ValidationError('Unsupported update signing purpose.')
    key=hmac.new(settings.SECRET_KEY.encode('utf-8'),b'isurvix-update-bridge-v1',hashlib.sha256).digest()
    return hmac.new(key,domain.encode('ascii')+b'\n'+canonical(payload),hashlib.sha256).hexdigest()


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError()
        result[key]=value
    return result


def _read_json(path,maximum=131072):
    path=Path(path)
    if not path.is_absolute() or any(part.is_symlink() or getattr(part,'is_junction',lambda:False)() for part in (path,*path.parents)):
        raise ValueError()
    if not path.is_file() or path.stat().st_size>maximum:raise ValueError()
    raw=path.read_bytes()
    if len(raw)>maximum:raise ValueError()
    return json.loads(raw.decode('utf-8'),object_pairs_hook=_unique),hashlib.sha256(raw).hexdigest()


def catalog():
    try:
        data,signature=_read_json(_setting('ISURVIX_UPDATE_CATALOG_FILE'))
        if not isinstance(data,dict) or set(data)!={'format','releases'} or data['format']!='isurvix-update-catalog-v1':raise ValueError()
        rows=data['releases']
        if not isinstance(rows,list) or len(rows)>128:raise ValueError()
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or set(row)-{'release_id','manifest_sha256','supported_from','editions','release_record_sha256'} or not {'release_id','manifest_sha256','supported_from','editions'}<=set(row):raise ValueError()
            if not isinstance(row['release_id'],str) or not SHA40.fullmatch(row['release_id']) or row['release_id'] in seen:raise ValueError()
            seen.add(row['release_id'])
            if not isinstance(row['manifest_sha256'],str) or not SHA64.fullmatch(row['manifest_sha256']):raise ValueError()
            supported=row['supported_from'];editions=row['editions']
            if not isinstance(supported,list) or not 1<=len(supported)<=128 or any(not isinstance(value,str) or not SHA40.fullmatch(value) for value in supported) or len(set(supported))!=len(supported):raise ValueError()
            if not isinstance(editions,list) or not editions or any(value not in ('cloud','customer') for value in editions) or len(set(editions))!=len(editions):raise ValueError()
            if 'release_record_sha256' in row and (not isinstance(row['release_record_sha256'],str) or not SHA64.fullmatch(row['release_record_sha256'])):raise ValueError()
        return rows,signature
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
        raise ValidationError('The trusted update catalog is unavailable or invalid. Ask the operator to configure the approved read-only catalog.') from None


def current_edition():
    value=_setting('ISURVIX_EDITION','customer')
    if value not in ('customer','cloud'):raise ValidationError('The server edition is not configured for updates.')
    return value


def available_releases():
    rows,signature=catalog();current=release_id();edition=current_edition()
    return [row for row in rows if current in row['supported_from'] and edition in row['editions'] and row['release_id']!=current],signature


def _bindings(request):
    return {'request_id':str(request.pk),'source_release':request.source_release,'target_release':request.target_release,
        'manifest_sha256':request.manifest_sha256,'catalog_sha256':request.catalog_sha256,'edition':request.edition,'nonce':request.nonce}


def request_update(actor,*,target_release,expected_current,request_key,maintenance_confirmed):
    owner(actor)
    try:key=uuid.UUID(str(request_key))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Use the request key from the Update Center form.') from None
    if not isinstance(target_release,str) or not SHA40.fullmatch(target_release) or not isinstance(expected_current,str) or not SHA40.fullmatch(expected_current):raise ValidationError('Choose an exact catalog release and expected installed version.')
    if maintenance_confirmed is not True:raise ValidationError('Confirm the maintenance window and verified backup/recovery plan.')
    with transaction.atomic():
        actor=get_user_model().objects.select_for_update().get(pk=actor.pk);owner(actor)
        existing=ServerUpdateRequest.objects.filter(request_key=key).first()
        if existing:
            if existing.target_release!=target_release or existing.source_release!=expected_current or existing.requested_by_id!=actor.pk:
                raise ValidationError('This request key already belongs to another update.',code='conflict')
            return existing
        if expected_current!=release_id():raise ValidationError('The installed version changed. Refresh the Update Center.',code='conflict')
        choices,catalog_hash=available_releases()
        selected=next((row for row in choices if row['release_id']==target_release),None)
        if selected is None:raise ValidationError('This target is not approved for the current source version and edition.')
        if ServerUpdateRequest.objects.filter(active=True).exists():raise ValidationError('Another update request is active. Finish or recover it before requesting another.',code='conflict')
        try:
            with transaction.atomic():
                request=ServerUpdateRequest.objects.create(request_key=key,requested_by=actor,source_release=expected_current,
                    target_release=target_release,manifest_sha256=selected['manifest_sha256'],catalog_sha256=catalog_hash,
                    release_record_sha256=selected.get('release_record_sha256',''),edition=current_edition(),maintenance_confirmed=True)
        except IntegrityError:raise ValidationError('Another update request is active. Refresh before retrying.',code='conflict') from None
        details={'request_id':str(request.pk),'source_release':expected_current,'target_release':target_release,'manifest_sha256':request.manifest_sha256}
        ServerUpdateEvent.objects.create(request=request,sequence=0,status='pending',receipt_digest=hashlib.sha256(canonical(details)).hexdigest(),details=details)
        GovernanceAudit.objects.create(action='server_update_requested',actor=actor,actor_name=actor.username,details=details)
        return request


def export_request(request_id):
    with transaction.atomic():
        request=ServerUpdateRequest.objects.select_for_update().select_related('requested_by').get(pk=request_id)
        owner(request.requested_by)
        if request.maintenance_confirmed is not True:raise ValidationError('Maintenance was not confirmed for this request.')
        if request.status not in ACTIVE:raise ValidationError('This update is no longer active.')
        if request.source_release!=release_id():raise ValidationError('The installed version no longer matches this request. Preserve the journal and recover explicitly.')
        rows,catalog_hash=catalog()
        entry=next((row for row in rows if row['release_id']==request.target_release),None)
        if (catalog_hash!=request.catalog_sha256 or not entry or entry['manifest_sha256']!=request.manifest_sha256
            or request.source_release not in entry['supported_from'] or request.edition not in entry['editions'] or request.edition!=current_edition()):
            raise ValidationError('The trusted catalog or supported update path changed. No package was executed.')
        now=int(time.time())
        payload={'format':'isurvix-update-request-v1',**_bindings(request),'request_key':str(request.request_key),
            'maintenance_confirmed':request.maintenance_confirmed,'release_record_sha256':request.release_record_sha256,
            'issued_at':now,'expires_at':now+300}
        return {'payload':payload,'signature':sign_payload('request-v1',payload)}


def withdraw_request(actor,request_id):
    """Withdraw only before the host's acknowledged verified phase.

    The row lock and occupied sequence make withdrawal race safely with the
    host ACK. A host must receive a successful verified/applying ACK before
    stopping writers; an earlier export alone never grants that transition.
    """
    owner(actor)
    with transaction.atomic():
        request=ServerUpdateRequest.objects.select_for_update().get(pk=request_id)
        if request.status=='failed' and request.error_code=='cancelled':return request
        if request.status!='pending' or request.last_sequence!=0:
            raise ValidationError('The host has already verified or started this request. Use the authorized host recovery process; it cannot be withdrawn here.')
        details={'request_id':str(request.pk),'origin':'current_platform_owner','error_code':'cancelled'}
        ServerUpdateEvent.objects.create(request=request,sequence=1,status='failed',error_code='cancelled',
            receipt_digest=hashlib.sha256(canonical(details)).hexdigest(),details=details)
        request.status='failed';request.error_code='cancelled';request.last_sequence=1;request.active=False;request.save()
        GovernanceAudit.objects.create(action='server_update_withdrawn',actor=actor,actor_name=actor.username,details=details)
        return request


def apply_receipt(signed,*,actor=None):
    if actor is not None:owner(actor)
    if not isinstance(signed,dict) or set(signed)!={'payload','signature'}:raise ValidationError('The host update receipt is invalid.')
    payload=signed['payload'];signature=signed['signature']
    required={'format','request_id','source_release','target_release','manifest_sha256','catalog_sha256','edition','nonce','sequence','status','release_id','error_code','at'}
    optional={'backup_manifest_sha256','evidence_inventory_sha256'}
    if not isinstance(payload,dict) or not required<=set(payload) or set(payload)-required-optional or len(canonical(signed))>16384:raise ValidationError('The host update receipt has unsupported fields.')
    if payload['format']!='isurvix-update-receipt-v1' or not isinstance(signature,str) or not SHA64.fullmatch(signature) or not hmac.compare_digest(sign_payload('receipt-v1',payload),signature):raise ValidationError('The host update receipt signature is invalid.')
    if type(payload['sequence']) is not int or not 1<=payload['sequence']<=1000 or type(payload['at']) is not int or payload['at']<0:raise ValidationError('The host update receipt sequence or timestamp is invalid.')
    if not isinstance(payload['status'],str) or not isinstance(payload['error_code'],str) or payload['status'] not in TRANSITIONS or payload['error_code'] not in ERRORS:raise ValidationError('The host update receipt state is invalid.')
    if any(not isinstance(payload[key],str) or not SHA64.fullmatch(payload[key]) for key in optional if key in payload):raise ValidationError('The host recovery proof digest is invalid.')
    try:request_id=uuid.UUID(str(payload['request_id']))
    except (ValueError,TypeError,AttributeError):raise ValidationError('The host update request identity is invalid.') from None
    proof=hashlib.sha256(canonical(signed)).hexdigest()
    with transaction.atomic():
        request=ServerUpdateRequest.objects.select_for_update().get(pk=request_id)
        if any(payload[key]!=value for key,value in _bindings(request).items()):raise ValidationError('The host receipt belongs to different update inputs.')
        previous=ServerUpdateEvent.objects.filter(request=request,sequence=payload['sequence']).first()
        if previous:
            if previous.receipt_digest!=proof:raise ValidationError('A different host receipt already occupies this sequence.')
            return request
        if payload['sequence']!=request.last_sequence+1:raise ValidationError('Host update receipts are missing or out of order. Preserve the journal and retry reconciliation.')
        state=payload['status']
        if state not in TRANSITIONS[request.status]:raise ValidationError('The host update state transition is not permitted.')
        if payload['release_id'] not in (request.source_release,request.target_release):raise ValidationError('The host receipt names an unrelated installed release.')
        if state=='completed' and (payload['release_id']!=request.target_release or release_id()!=request.target_release):raise ValidationError('The target release is not running. Completion cannot be recorded.')
        if state=='rolled_back' and (payload['release_id']!=request.source_release or release_id()!=request.source_release):raise ValidationError('The original release is not running. Recovery cannot be recorded.')
        if state in ('verified','applying','completed') and payload['error_code']:raise ValidationError('A successful host phase cannot contain a failure code.')
        if state=='failed' and not payload['error_code']:raise ValidationError('A stopped host update requires a safe error code.')
        ServerUpdateEvent.objects.create(request=request,sequence=payload['sequence'],status=state,error_code=payload['error_code'],receipt_digest=proof,details=payload)
        request.status=state;request.last_sequence=payload['sequence']
        request.active=state in ACTIVE or (state=='failed' and payload['error_code'] in RECOVERY_REQUIRED)
        request.error_code=payload['error_code'];request.save()
        GovernanceAudit.objects.create(action='server_update_status',actor=actor,actor_name=getattr(actor,'username','root-local bridge'),
            details={'request_id':str(request.pk),'sequence':request.last_sequence,'status':state,'error_code':request.error_code,'receipt_digest':proof})
        return request


def reconcile_receipts(actor,request_id):
    owner(actor)
    request=ServerUpdateRequest.objects.get(pk=request_id)
    try:
        root=Path(_setting('ISURVIX_UPDATE_RECEIPTS_ROOT'))
        folder=root/str(request.pk)
        if not root.is_absolute() or any(path.is_symlink() or getattr(path,'is_junction',lambda:False)() for path in (folder,*folder.parents)):
            raise ValueError()
        if not folder.exists():return request,0
        paths=sorted(folder.iterdir())
        if len(paths)>1000 or any(not re.fullmatch(r'\d{6}\.json',path.name) for path in paths):raise ValueError()
        count=0
        for path in paths:
            signed,_=_read_json(path,16384)
            if signed.get('payload',{}).get('sequence')!=int(path.stem):raise ValueError()
            apply_receipt(signed,actor=actor);count+=1
        return ServerUpdateRequest.objects.get(pk=request.pk),count
    except (OSError,ValueError,TypeError,KeyError,UnicodeError,RecursionError):
        raise ValidationError('The private host receipt spool is unavailable or invalid. No success was inferred.') from None
