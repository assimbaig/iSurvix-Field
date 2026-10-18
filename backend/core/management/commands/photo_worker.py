"""Run a single durable local photo consumer independently of web requests."""
import time
from django.conf import settings
from django.db import OperationalError, close_old_connections
from django.core.management.base import BaseCommand, CommandError
from core.photo_queue import process_next
from core.local_ai import InferenceBusy

class Command(BaseCommand):
    help='Process local photo jobs; restart safely after interruption.'
    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
    def handle(self, *args, **options):
        if not getattr(settings,'LOCAL_AI_ENABLED',False):
            raise CommandError('Use checklist.settings_local for the local photo worker.')
        self.stdout.write('Local photo worker started. Press Ctrl+C to stop.')
        try:
            while True:
                try:
                    worked=process_next()
                except InferenceBusy:
                    worked=False
                except OperationalError as exc:
                    message=str(exc).lower()
                    if not any(marker in message for marker in ('database is locked','database table is locked','database schema is locked','database is busy','database table is busy')):
                        raise
                    # A transient SQLite writer must not terminate the durable consumer.
                    # Leave job state untouched; its lease/checkpoint handles recovery.
                    close_old_connections()
                    worked=False
                if options['once']:
                    return
                if not worked:
                    time.sleep(2)
        except KeyboardInterrupt:
            self.stdout.write('Worker stopped. Interrupted work resumes after lease expiry.')
