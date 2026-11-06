from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from .workflow_email import install_receivers
        install_receivers()
