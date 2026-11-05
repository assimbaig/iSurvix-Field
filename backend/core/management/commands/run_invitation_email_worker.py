"""Run the existing application's bounded, durable invitation-email outbox."""
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from core.invitation_email import process_next_email, retry_failed_emails
from core.notification_email import load_config, NotificationEmailError


class Command(BaseCommand):
    help = 'Deliver queued invitations through the configured Microsoft 365 sender.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process at most one eligible invitation.')
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
        try:
            while True:
                close_old_connections()
                processed = process_next_email()
                if options['once']:
                    self.stdout.write('Processed one invitation.' if processed else 'No eligible invitation emails.')
                    return
                if not processed:
                    time.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write('Email worker stopped; persistent delivery state retained.')
