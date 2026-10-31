"""Capture quiesced persistent SQLite/media into a new private directory."""
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from core.operations_backup import create_backup
from core.operations_service import release_id


class Command(BaseCommand):
    help='Create a private verified SQLite/media backup after stopping all writers. Never overwrites a target.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        parser.add_argument('--destination',required=True)
        parser.add_argument('--quiesced',action='store_true')
    def handle(self,*args,**options):
        database=settings.DATABASES['default']
        if database['ENGINE']!='django.db.backends.sqlite3':raise CommandError('This backup command supports the configured SQLite deployment only.')
        try:
            result=create_backup(Path(database['NAME']),Path(settings.MEDIA_ROOT),Path(options['destination']),release_id=release_id(),quiesced=options['quiesced'])
        except (ValueError,OSError) as error:raise CommandError(str(error)) from None
        self.stdout.write(json.dumps(result,sort_keys=True))
