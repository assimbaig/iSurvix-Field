"""Do not persist bearer invitation URLs in Django's request/server logs."""
import logging
import re


class RedactInvitations(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        record.msg = re.sub(r'(/governance/invite/)([^/\s?]+)', r'\1[redacted]', message)
        record.args = ()
        return True
