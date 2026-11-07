"""Remove invitation and password-reset bearers from application diagnostics.

The filter keeps status codes, error messages and traceback structure. It never
changes the live HttpRequest or disables handlers to conceal rejected requests.
"""
from copy import copy
import logging
import re

_BEARER_PATHS=(
 re.compile(r'(/governance/invite/)([^/\s?\#\"\'<>]+)',re.I),
 # Match malformed/case-variant request IDs too: a 404 can still contain a live
 # bearer copied from the canonical link. Do not redact reset request/sent URLs.
 re.compile(r'(/account/password-reset/[^/\s?\#\"\'<>]+/)([^/\s?\#\"\'<>]+)',re.I),
)

def _redactor(values):
 tokens={match.group(2) for value in values if isinstance(value,str)
         for pattern in _BEARER_PATHS for match in pattern.finditer(value)
         if match.group(2)!='[redacted]'}
 def redact(value):
  if not isinstance(value,str):return value
  for pattern in _BEARER_PATHS:value=pattern.sub(r'\1[redacted]',value)
  # A formatter/exception can echo the same bearer without its path, including
  # in a query value. Its path above establishes exactly what must be removed.
  for token in sorted(tokens,key=len,reverse=True):value=value.replace(token,'[redacted]')
  return value
 return redact

class RedactInvitations(logging.Filter):
 def filter(self,record):
  message=record.getMessage()
  trace=logging.Formatter().formatException(record.exc_info) if record.exc_info else record.exc_text
  request=getattr(record,'request',None)
  request_values=[]
  if request is not None:
   request_values=[getattr(request,'path',''),getattr(request,'path_info','')]
   if hasattr(request,'get_full_path'):request_values.append(request.get_full_path())
  redact=_redactor([message,trace,*request_values,*record.__dict__.values()])
  record.msg=redact(message);record.args=()
  for name,value in list(record.__dict__.items()):
   if isinstance(value,str):setattr(record,name,redact(value))
  if trace:
   record.exc_text=redact(trace)
   # Preserve the already-formatted traceback; handlers must not re-render the
   # original exception's raw URL after filtering.
   record.exc_info=None
  if request is not None and any(redact(value)!=value for value in request_values):
   safe_request=copy(request)
   for name in ('path','path_info'):
    if hasattr(request,name):setattr(safe_request,name,redact(getattr(request,name)))
   if hasattr(request,'META'):safe_request.META={key:redact(value) for key,value in request.META.items()}
   record.request=safe_request
  return True
