"""Fixed, escaped email presentation; custom messages remain plain-text inputs."""
from html import escape
import re
from urllib.parse import urlsplit

DISCLAIMER=('This automated message is informational; please do not reply. '
    'Use iField for current task details and authorised decisions. '
    'Keep private invitation and password-reset links confidential.')


def present_email(subject,body):
    from .invitation_email import _public_origin
    origin=_public_origin()
    plain=body+'\n\n—\niField | iSurvix\n'+DISCLAIMER
    pieces=[];position=0
    for match in re.finditer(r'https://[^\s<>"\']+',body):
        pieces.append(escape(body[position:match.start()]))
        url=match[0];parts=urlsplit(url)
        if parts.netloc==urlsplit(origin).netloc and not parts.username and not parts.password:
            pieces.append('<a href="'+escape(url,quote=True)+'">'+escape(url)+'</a>')
        else:pieces.append(escape(url))
        position=match.end()
    pieces.append(escape(body[position:]))
    html=('<!doctype html><html><body style="margin:0;background:#f4f6f8;color:#1d2939;font-family:Arial,sans-serif">'
        '<div style="max-width:640px;margin:20px auto;padding:24px;background:#fff;border:1px solid #dce3ea">'
        f'<img src="{escape(origin,quote=True)}/static/core/img/ifield-logo.webp" alt="iField" width="144" height="58" style="object-fit:contain">'
        f'<h1 style="font-size:20px;line-height:1.4">{escape(subject)}</h1>'
        '<div style="font-size:14px;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere">'+''.join(pieces)+'</div>'
        '<div style="margin-top:24px;padding-top:14px;border-top:1px solid #dce3ea;font-size:12px;line-height:1.5">'
        '<strong>iField | iSurvix</strong><br>'+escape(DISCLAIMER)+'</div></div></body></html>')
    return plain,html
