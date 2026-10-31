"""Bounded provider transport. Remote destinations belong to the operator, never a browser."""
import hashlib
import json
import os
import re
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,ProxyHandler
from django.conf import settings
from django.core.exceptions import ValidationError
from . import local_ai


def registry_entry(alias):
    registry=getattr(settings,'AI_PROVIDER_REGISTRY',{})
    entry=registry.get(alias) if isinstance(registry,dict) else None
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',alias or '') or not isinstance(entry,dict):
        raise ValidationError('The approved API provider alias is unavailable.')
    endpoint=entry.get('endpoint','')
    try:parts=urlsplit(endpoint);port=parts.port
    except (ValueError,TypeError):raise ValidationError('The approved API endpoint is invalid.') from None
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.path not in ('','/') or parts.query or parts.fragment:
        raise ValidationError('The approved API endpoint must be a private HTTPS origin without credentials.')
    env=entry.get('credential_env','')
    if env and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,100}',env):
        raise ValidationError('The provider credential reference is invalid.')
    return {'endpoint':endpoint.rstrip('/'),'credential_env':env}


def endpoint_fingerprint(alias):
    return hashlib.sha256(json.dumps(registry_entry(alias),sort_keys=True).encode()).hexdigest()


class Provider:
    def __init__(self,kind,model,policy):
        self.kind,self.model,self.policy=kind,model,policy
        self.base_url=getattr(settings,'PHOTO_OLLAMA_BASE_URL',settings.OLLAMA_BASE_URL) if kind=='local' else ''

    def request(self,path,payload=None,**ignored):
        if path not in ('/api/tags','/api/show','/api/chat'):
            raise ValidationError('Unsupported provider operation.')
        if self.kind=='local':
            if not getattr(settings,'LOCAL_AI_ENABLED',False):
                raise ValidationError('Local inference is disabled on this host. Use the approved local worker.',code='local_unavailable')
            return local_ai.ollama(path,payload,base_url=self.base_url,timeout=self.policy['request_timeout'])
        entry=registry_entry(self.policy['api_endpoint'])
        if endpoint_fingerprint(self.policy['api_endpoint'])!=self.policy['endpoint_fingerprint']:
            raise ValidationError('The approved API connection changed. Preserve this job and use a new submission.')
        secret=os.environ.get(entry['credential_env'],'') if entry['credential_env'] else ''
        if entry['credential_env'] and not secret:
            raise ValidationError('The approved provider credential is unavailable; contact the platform operator.')
        headers={'Content-Type':'application/json'}
        if secret:headers['Authorization']='Bearer '+secret
        body=json.dumps(payload,allow_nan=False).encode() if payload is not None else None
        req=Request(entry['endpoint']+path,data=body,headers=headers)
        # TLS verification remains enabled; ignore proxies and reject credential redirects.
        with build_opener(ProxyHandler({}),local_ai.NoRedirect()).open(req,timeout=self.policy['request_timeout']) as response:
            raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise ValidationError('The provider response exceeds its processing bound.')
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValidationError('The provider response is invalid.')
        return result

    def verify(self,model,base_url=None):
        tags=self.request('/api/tags').get('models',[])
        if not isinstance(tags,list) or not any(isinstance(row,dict) and row.get('name')==model and not row.get('remote_model') and not row.get('remote_host') for row in tags):
            raise ValidationError('The selected vision model is not available at the approved provider.')
        details=self.request('/api/show',{'model':model})
        capabilities=details.get('capabilities',[])
        if not isinstance(capabilities,list) or 'vision' not in capabilities or details.get('remote_model') or details.get('remote_host'):
            raise ValidationError('The selected provider model does not support image analysis.')


def provider_for(kind,policy):
    return Provider(kind,policy['local_model'] if kind=='local' else policy['api_model'],policy)
