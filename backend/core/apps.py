from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from .workflow_email import install_receivers
        install_receivers()
        from django.contrib.auth.signals import user_logged_in
        from .release_history import record_login_release
        user_logged_in.connect(record_login_release,dispatch_uid="core.installed_release_login")
