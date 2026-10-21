"""Project-Admin provisioning; secret written once into an exclusive private file."""
import json
import os
import subprocess
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core import remote_worker_service as service
from core.remote_worker_client import RemoteSurveyClient, secure_private_path


class Command(BaseCommand):
    help = 'Provision/revoke an expiring project-scoped local PC worker credential. Never prints secrets.'

    def add_arguments(self, parser):
        parser.add_argument('--admin', required=True)
        parser.add_argument('--project', action='append', type=int, default=[])
        parser.add_argument('--server-url')
        parser.add_argument('--output')
        parser.add_argument('--hours', type=int, default=720)
        parser.add_argument('--label', default='Local survey PC')
        parser.add_argument('--revoke')

    def handle(self, *args, **options):
        created_output = None
        try:
            admin = get_user_model().objects.select_related('profile').get(username=options['admin'])
            if options['revoke']:
                service.revoke(admin, options['revoke'])
                self.stdout.write('Worker credential revoked. Existing project jobs remain queued/recoverable.')
                return
            if not options['project'] or not options['server_url'] or not options['output']:
                raise CommandError('Provide --project, --server-url and a new private --output file.')
            output = Path(options['output']).resolve()
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Validate URL before creating a credential. A placeholder credential
            # is never sent or persisted by the client constructor.
            RemoteSurveyClient(options['server_url'], 'validation-only', output.parent / 'remote-worker-cache')
            with transaction.atomic():
                credential, token = service.provision(admin, options['project'], options['label'], options['hours'])
                fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                created_output = output
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    secure_private_path(output)
                    json.dump({'server_url': options['server_url'].rstrip('/'), 'token': token,
                               'credential_id': str(credential.pk), 'expires_at': credential.expires_at.isoformat()}, handle, indent=2)
            self.stdout.write('Worker configuration written to the requested private file. Transfer securely to the local PC; never commit it.')
        except (get_user_model().DoesNotExist, PermissionDenied, ValidationError, OSError, ValueError, subprocess.SubprocessError):
            if created_output is not None:
                created_output.unlink(missing_ok=True)
            raise CommandError('Worker provisioning failed. Check the current project Admin, project scope, URL and exclusive private output path.') from None
