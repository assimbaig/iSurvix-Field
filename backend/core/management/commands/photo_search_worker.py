"""Independent CPU batched retrieval; does not take the native model lease."""
import time
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import close_old_connections
from core.photo_search import process_next

class Command(BaseCommand):
    help='Generate fast, unverified photo/checklist suggestions independently of detailed verification.'
    def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        if not getattr(settings,'LOCAL_AI_ENABLED',False):raise CommandError('Local settings are required.')
        self.stdout.write('Batched photo matching worker started; suggestions never approve evidence.')
        try:
            while True:
                worked=False
                try:worked=process_next()
                except Exception as error:
                    # Never log raw model/image data. Scoped UI state has a safe error.
                    self.stderr.write('Fast matching deferred: '+type(error).__name__)
                    close_old_connections()
                if options['once']:return
                if not worked:time.sleep(5)
        except KeyboardInterrupt:pass
