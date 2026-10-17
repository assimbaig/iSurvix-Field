"""Initialize a new local database without default credentials or production data."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'checklist.settings_local'
import django

def main():
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from core.models import Profile
    call_command('check')
    call_command('migrate', interactive=False)
    User = get_user_model()
    if not User.objects.filter(is_superuser=True).exists():
        print('\nCreate your local administrator. Choose a username and password.\n')
        call_command('createsuperuser', interactive=True)
    # Give only the existing local superuser the app's admin profile.
    for user in User.objects.filter(is_superuser=True):
        profile, _ = Profile.objects.get_or_create(user=user)
        if profile.role != Profile.Roles.ADMIN:
            profile.role = Profile.Roles.ADMIN
            profile.save(update_fields=['role'])
    print('\nLocal database ready. No production data has been imported.')

if __name__ == '__main__':
    main()
