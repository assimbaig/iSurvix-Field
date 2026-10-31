"""Container-local readiness; never calls the local PC or model."""
import json
import os
from urllib.request import ProxyHandler,Request,build_opener

host=os.environ['DJANGO_ALLOWED_HOSTS'].split(',')[0].strip()
request=Request('http://127.0.0.1:8000/ops/health/ready/',headers={'Host':host,'X-Forwarded-Proto':'https'})
with build_opener(ProxyHandler({})).open(request,timeout=3) as response:
    result=json.load(response)
    if response.status!=200 or result.get('status')!='ready':raise SystemExit(1)
