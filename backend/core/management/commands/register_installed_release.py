from django.core.management.base import BaseCommand, CommandError
from core.release_history import register_current_release


class Command(BaseCommand):
    help='Record immutable installed release notes (no email or engineering writes).'
    def handle(self,*args,**kwargs):
        try:record,created=register_current_release()
        except ValueError as error:raise CommandError(str(error)) from None
        self.stdout.write('Release V'+record.version+(' recorded.' if created else ' already recorded.'))
