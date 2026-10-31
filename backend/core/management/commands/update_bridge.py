"""Root-local bridge executed inside the installed application container."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import PermissionDenied,ValidationError
from core import update_service as service
from core.update_models import ServerUpdateRequest


class Command(BaseCommand):
    help='Export a freshly authorized signed update request or ingest a signed host receipt. This does not run Docker or install updates.'
    def add_arguments(self,parser):
        parser.add_argument('action',choices=['export','receipt'])
        parser.add_argument('request_id',nargs='?')
        parser.add_argument('--receipt-file',type=Path)
    def handle(self,*args,**options):
        try:
            if options['action']=='export':
                if not options['request_id'] or options['receipt_file']:raise ValidationError('Supply the saved request UUID only.')
                result=service.export_request(options['request_id'])
            else:
                if options['request_id'] or not options['receipt_file']:raise ValidationError('Supply one private host receipt file only.')
                signed,_=service._read_json(options['receipt_file'],16384)
                saved=service.apply_receipt(signed)
                result={'request_id':str(saved.pk),'status':saved.status,'sequence':saved.last_sequence}
        except (PermissionDenied,ValidationError,ServerUpdateRequest.DoesNotExist,ValueError,TypeError,OSError):
            raise CommandError('The update bridge could not verify the current request or receipt. No package was executed; inspect the saved request and trusted operator inputs.') from None
        self.stdout.write(json.dumps(result,sort_keys=True))
