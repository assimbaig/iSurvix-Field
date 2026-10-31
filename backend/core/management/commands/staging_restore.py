"""Verify a private backup and restore into a new disposable destination only."""
import json
from django.core.management.base import BaseCommand,CommandError
from core.operations_backup import restore_backup


class Command(BaseCommand):
    help='Restore a complete private backup into a NEW directory; never modifies current database/media.'
    requires_system_checks=[]
    def add_arguments(self,parser):
        parser.add_argument('--backup',required=True)
        parser.add_argument('--destination',required=True)
    def handle(self,*args,**options):
        try:result=restore_backup(options['backup'],options['destination'])
        except (ValueError,OSError) as error:raise CommandError(str(error)) from None
        self.stdout.write(json.dumps(result,sort_keys=True))
