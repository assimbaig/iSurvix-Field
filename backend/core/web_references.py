"""Explicit public-keyword lookup; references never become survey evidence."""
import json
import os
import re
import hashlib
import time
import unicodedata
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

import requests
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

MAX_BYTES=256*1024
MAX_RESULTS=5
NOTICE='Unverified external references only. These results do not establish site evidence, checklist answers or engineering approval.'


class ReferenceError(ValueError):
    def __init__(self,code,message,status=400):
        self.code,self.status=code,status
        super().__init__(message)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.suppressed=0

    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.suppressed+=1

    def handle_endtag(self,tag):
        if tag in {'script','style'} and self.suppressed:self.suppressed-=1

    def handle_data(self,data):
        if not self.suppressed:self.parts.append(data)


def plain(value,limit):
    if not isinstance(value,str):return ''
    parser=PlainText()
    parser.feed(value[:20000])
    return re.sub(r'\s+',' ',''.join(parser.parts)).strip()[:limit]


def validate_query(query):
    if not isinstance(query,str) or any(unicodedata.category(char).startswith('C') for char in query):
        raise ReferenceError('invalid_query','Enter public equipment keywords without control characters.')
    query=query.strip()
    if not 1<=len(query)<=160 or len(query.split())>25:
        raise ReferenceError('invalid_query','Enter 1–160 characters and at most 25 public equipment keywords.')
    return query


def safe_url(value):
    """Allow ordinary public DNS links, without resolving/fetching destinations.

    Browsers accept integer/hex/short IPv4 spellings that Python's IP parser
    treats as names. DNS-only ASCII authorities avoid that disagreement and
    reject IPv6 literals too. This is syntactic filtering, not a DNS guarantee.
    """
    if not isinstance(value,str) or len(value)>2048 or '\\' in value or any(
            char.isspace() or unicodedata.category(char).startswith('C') for char in value):return None
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:return None
        authority=parsed.netloc
        if not authority.isascii() or any(char in authority for char in '%@[]'):return None
        host=parsed.hostname
        if len(host)>253 or host.endswith('.'):return None
        labels=host.split('.')
        if len(labels)<2 or not re.fullmatch(r'[a-z]{2,63}',labels[-1]):return None
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels):return None
        local_suffixes={'localhost','local','localdomain','internal','lan','home','home.arpa','test','invalid','onion'}
        if any(host==suffix or host.endswith('.'+suffix) for suffix in local_suffixes):return None
        if ':' in authority:
            # Only canonical default ports; reject empty/zero-padded ports and
            # alternate local-service ports before the browser normalizes them.
            if authority.count(':')!=1 or authority.rsplit(':',1)[1]!=('443' if parsed.scheme=='https' else '80'):return None
    except ValueError:return None
    return value


def fetch_json(url,params,headers):
    response=None
    started=time.monotonic()
    try:
        response=requests.get(url,params=params,headers=headers,timeout=(3,8),stream=True,allow_redirects=False)
        if response.status_code!=200:
            raise ReferenceError('provider_unavailable','The reference provider is unavailable. Retry later.',503)
        raw=bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if time.monotonic()-started>12:
                raise ReferenceError('provider_timeout','The reference search timed out. Retry later.',504)
            raw.extend(chunk)
            if len(raw)>MAX_BYTES:
                raise ReferenceError('provider_response_too_large','The reference provider returned too much data.',502)
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValueError()
        return result
    except requests.exceptions.Timeout as exc:
        raise ReferenceError('provider_timeout','The reference search timed out. Retry later.',504) from exc
    except requests.exceptions.RequestException as exc:
        raise ReferenceError('provider_unavailable','The reference provider could not be reached securely. Retry later.',503) from exc
    except (ValueError,TypeError,UnicodeError) as exc:
        if isinstance(exc,ReferenceError):raise
        raise ReferenceError('invalid_provider_response','The reference provider returned an unreadable response.',502) from exc
    finally:
        if response is not None:response.close()


def search(query,provider='wikipedia'):
    query=validate_query(query)
    headers={'User-Agent':'iSurvixField-public-references/1.0 (https://github.com/assimbaig/iSurvix-Field)',
        'Accept':'application/json'}
    if provider=='wikipedia':
        label,scope='Wikipedia encyclopedia references','encyclopedia'
        payload=fetch_json('https://en.wikipedia.org/w/rest.php/v1/search/page',{'q':query,'limit':MAX_RESULTS},headers)
        rows=payload.get('pages')
    elif provider=='brave':
        label,scope='Brave web references','web'
        key=os.environ.get('BRAVE_SEARCH_API_KEY','').strip()
        if not key:raise ReferenceError('not_configured','Full web search is not configured. An owner-provided Brave Search API key is required.',503)
        headers['X-Subscription-Token']=key
        payload=fetch_json('https://api.search.brave.com/res/v1/web/search',{'q':query,'count':MAX_RESULTS},headers)
        web=payload.get('web',{})
        rows=web.get('results',[]) if isinstance(web,dict) else None
    else:
        raise ReferenceError('invalid_provider','Choose Wikipedia encyclopedia references or configured Brave web search.')
    if not isinstance(rows,list):raise ReferenceError('invalid_provider_response','The reference provider returned an unreadable response.',502)
    results=[]
    for row in rows[:MAX_RESULTS]:
        if not isinstance(row,dict):continue
        title=plain(row.get('title'),240)
        if provider=='wikipedia':
            key=row.get('key')
            url='https://en.wikipedia.org/wiki/'+quote(key,safe='') if isinstance(key,str) and 1<=len(key)<=512 else None
            snippet=plain(row.get('excerpt') or row.get('description'),1200)
            source='Wikipedia'
        else:
            url=safe_url(row.get('url'))
            snippet=plain(row.get('description'),1200)
            source=urlsplit(url).hostname if url else ''
        if not title or not url:continue
        results.append({'title':title,'url':url,'snippet':snippet,'source':source})
    return {'ok':True,'provider':provider,'provider_label':label,'scope':scope,'query':query,
        'fetched_at':timezone.now().isoformat(),'reference_only':True,'verified':False,'notice':NOTICE,'results':results}


def user_search(actor_id,query,provider):
    query=validate_query(query)
    if provider not in ('wikipedia','brave'):
        raise ReferenceError('invalid_provider','Choose Wikipedia encyclopedia references or configured Brave web search.')
    # Cache keys contain neither user keywords nor credentials. A duplicate
    # explicit search reuses its timestamped response for one minute.
    signature=hashlib.sha256(json.dumps([actor_id,provider,query]).encode()).hexdigest()
    # Pre-WS1 entries may contain result URLs accepted by the earlier policy.
    # Do not serve those records after the destination policy changes.
    result_key='public-reference-result-ws1:'+signature
    saved=cache.get(result_key)
    if saved is not None:return saved
    inflight_key='public-reference-inflight:'+signature
    if not cache.add(inflight_key,True,timeout=30):
        raise ReferenceError('search_in_progress','This reference search is already running. Wait for its response.',429)
    try:
        limit_key='public-reference-limit:'+str(actor_id)+':'+str(int(time.time())//60)
        if cache.add(limit_key,1,timeout=65):count=1
        else:
            try:count=cache.incr(limit_key)
            except ValueError:
                cache.set(limit_key,1,timeout=65);count=1
        if count>10:raise ReferenceError('rate_limited','Wait a minute before another reference search.',429)
        result=search(query,provider)
        cache.set(result_key,result,timeout=60)
        return result
    finally:
        cache.delete(inflight_key)


@login_required
@require_POST
def lookup(request,checklist_id):
    from .category_intake import access,current_revision
    from .qa_matching import require_revision
    from .survey_processing import current
    c,_=access(request,checklist_id,quality=True)
    try:
        if len(request.body)>4096:raise ReferenceError('invalid_request','The keyword request is too large.',413)
        try:
            data=json.loads(request.body)
        except (ValueError,UnicodeError) as exc:
            raise ReferenceError('invalid_request','Enter a valid keyword search request.') from exc
        if not isinstance(data,dict) or set(data)-{'revision_id','source_digest','query','provider'}:
            raise ReferenceError('invalid_request','Send only the explicit keywords, provider and current revision identity.')
        revision=current_revision(c)
        if not revision:raise ValidationError('This evidence has not been submitted.')
        require_revision(revision,data)
        if not current(revision):raise ValidationError('The submitted evidence changed. Refresh the QA workspace.')
        result=user_search(request.user.pk,data.get('query'),data.get('provider','wikipedia'))
        response=JsonResponse(result)
    except ReferenceError as exc:
        response=JsonResponse({'ok':False,'code':exc.code,'error':str(exc),'reference_only':True},status=exc.status)
    except ValidationError as exc:
        response=JsonResponse({'ok':False,'code':'stale_revision','error':'; '.join(exc.messages),'reference_only':True},status=409)
    response['Cache-Control']='private, no-store'
    return response
