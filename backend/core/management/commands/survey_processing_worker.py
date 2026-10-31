"""Persistent background survey evidence/checklist/drawing worker."""
import time
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, OperationalError
from core.survey_processing import process_next


class Command(BaseCommand):
    help = 'Process opted-in survey submissions; resume persisted source checkpoints after interruption.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--configured-providers',action='store_true',help='Process only approved company HTTPS-primary policies; does not enable local inference.')

    def handle(self, *args, **options):
        if not getattr(settings, 'LOCAL_AI_ENABLED', False) and not options['configured_providers']:
            raise CommandError('Use the configured local Ollama settings for this worker.')
        self.stdout.write('AI checklist and drawing worker started. AI cannot approve or release outputs.')
        try:
            while True:
                worked = False
                try:
                    worked = process_next(configured_providers=True) if options['configured_providers'] else process_next()
                except OperationalError:
                    close_old_connections()
                    self.stderr.write('Database temporarily unavailable; saved jobs will resume.')
                if options['once']:
                    return
                if not worked:
                    time.sleep(3)
        except KeyboardInterrupt:
            self.stdout.write('Worker stopped; persisted source checkpoints are preserved.')
