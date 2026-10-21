"""Run on the local PC; the website and evidence store remain on the VPS."""
import json
import time
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.remote_worker_client import RemoteSurveyClient, WorkerConnectionError, WorkerAccessError


class Command(BaseCommand):
    help = 'Retrieve scoped survey jobs outbound over HTTPS and analyse using loopback Ollama.'

    def add_arguments(self, parser):
        parser.add_argument('--config', required=True, help='Private JSON file containing server_url, token and optional cache_dir.')
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        if not getattr(settings, 'LOCAL_AI_ENABLED', False):
            raise CommandError('Run this PC worker with the existing local Ollama settings.')
        configuration = Path(options['config']).resolve()
        try:
            config = json.loads(configuration.read_text(encoding='utf-8'))
            client = RemoteSurveyClient(config['server_url'], config['token'], config.get('cache_dir') or configuration.parent / 'remote-worker-cache')
        except (OSError, ValueError, KeyError, TypeError):
            raise CommandError('Read a valid private worker configuration created by the project Admin.') from None
        self.stdout.write('Outbound survey worker started. Ollama stays on loopback; AI cannot approve or release outputs.')
        delay = 3
        try:
            while True:
                try:
                    worked = client.process_once()
                    delay = 3 if worked else min(60, delay * 2)
                except (WorkerConnectionError, WorkerAccessError) as exc:
                    self.stderr.write(str(exc))
                    delay = min(60, delay * 2)
                    if options['once']:
                        raise CommandError(str(exc)) from None
                except Exception:
                    self.stderr.write('The local model is unavailable or incompatible. Start the configured Ollama instance; queued jobs remain on the server.')
                    delay = min(60, delay * 2)
                    if options['once']:
                        raise CommandError('The configured local model is unavailable or incompatible.') from None
                if options['once']:
                    return
                time.sleep(delay)
        except KeyboardInterrupt:
            self.stdout.write('Worker stopped. Saved server checkpoints and private local result cache are preserved.')
