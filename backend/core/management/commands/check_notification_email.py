"""Validate private configuration without sending mail or requesting OAuth tokens."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from core.invitation_email import _public_origin
from core.notification_email import load_config, NotificationEmailError, SENDER


class Command(BaseCommand):
    help = 'Check the invitation sender/configuration; no external request or email is sent.'

    def handle(self, *args, **options):
        self.stdout.write('Sender: ' + SENDER)
        if not settings.NOTIFICATION_EMAIL_ENABLED:
            raise CommandError('Invitation email is disabled; existing manual links remain available.')
        try:
            _public_origin()
            load_config()
        except NotificationEmailError as error:
            raise CommandError('Email configuration is incomplete: ' + error.code) from None
        self.stdout.write('Private configuration is valid. Microsoft authorization and live delivery are not verified by this check.')
