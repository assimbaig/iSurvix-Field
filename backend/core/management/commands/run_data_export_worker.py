"""Independent durable spreadsheet export worker; no AI or network dependency."""
import time
from django.core.management.base import BaseCommand
from django.db import OperationalError,close_old_connections
from core.export_service import process_next,expire_exports
class Command(BaseCommand):
 help='Prepare private Excel exports and expire artifacts; source records stay unchanged.'
 def add_arguments(self,parser):parser.add_argument('--once',action='store_true')
 def handle(self,*args,**options):
  self.stdout.write('Data export worker started. Queued work is retained across restarts.')
  try:
   while True:
    worked=False
    try:expire_exports();worked=process_next()
    except OperationalError:close_old_connections();self.stderr.write('Database temporarily unavailable; exports remain queued.')
    if options['once']:return
    if not worked:time.sleep(3)
  except KeyboardInterrupt:self.stdout.write('Stopped; queued exports and history are preserved.')
