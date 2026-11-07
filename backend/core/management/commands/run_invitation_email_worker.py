"""Run the existing application's bounded, durable invitation-email outbox."""
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from core.invitation_email import process_next_email, retry_failed_emails
from core.notification_email import load_config, NotificationEmailError
from core.workflow_email import (process_next_workflow_email, queue_daily_digests,
                                 retry_failed_workflow_emails)
from core.account_recovery import process_next_reset_email,retry_failed_reset_emails


class Command(BaseCommand):
    help = 'Deliver queued invitations and scoped workflow notifications through Microsoft 365.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process at most one eligible email.')
        parser.add_argument('--retry-failed', action='store_true', help='Explicitly requeue definite failures only; uncertain sends are never requeued.')
        parser.add_argument('--interval', type=int, default=5)

    def handle(self, *args, **options):
        if not settings.NOTIFICATION_EMAIL_ENABLED:
            raise CommandError('Invitation email is disabled. Configure and enable Microsoft 365 sending first.')
        if not 1 <= options['interval'] <= 300:
            raise CommandError('Use a polling interval from 1 to 300 seconds.')
        try:
            load_config()
        except NotificationEmailError as error:
            raise CommandError('Microsoft 365 email configuration is unavailable: ' + error.code) from None
        if options['retry_failed']:
            self.stdout.write(f'Requeued {retry_failed_emails()} definite failures. Uncertain sends retained.')
            self.stdout.write(f'Requeued {retry_failed_workflow_emails()} workflow failures. Uncertain sends retained.')
            self.stdout.write(f'Requeued {retry_failed_reset_emails()} valid password reset failures. Uncertain sends retained.')
        queue_offset = 0
        next_digest_check = 0
        try:
            while True:
                close_old_connections()
                if time.monotonic() >= next_digest_check:
                    queue_daily_digests()
                    next_digest_check = time.monotonic() + 60
                queues = [('invitation', process_next_email), ('recovery',process_next_reset_email), ('workflow', process_next_workflow_email)]
                queues=queues[queue_offset:]+queues[:queue_offset]
                processed = False
                processed_kind = None
                for kind, process in queues:
                    if process():
                        processed, processed_kind = True, kind
                        break
                queue_offset=(queue_offset+1)%len(queues)
                if options['once']:
                    self.stdout.write(({'invitation':'Processed one invitation.','recovery':'Processed one password reset email.'}.get(processed_kind,'Processed one workflow email.'))
                                      if processed else 'No eligible invitation or workflow emails.')
                    return
                if not processed:
                    time.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write('Email worker stopped; persistent delivery state retained.')
