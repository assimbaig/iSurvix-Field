"""Temporary password throttles are separate from intentional account locks.

Existing is_locked values have ambiguous provenance and are preserved for an
authorized administrator review instead of automatically unlocking accounts.
"""
from django.db import migrations,models


class Migration(migrations.Migration):
    dependencies=[('core','0051_consolidate_project_manager_admin')]
    operations=[migrations.AddField(model_name='profile',name='login_locked_until',
        field=models.DateTimeField(null=True,blank=True,editable=False))]
