"""Read-only transition impact; safe to run before applying migration 0051."""
import importlib
import json
from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help='Report legacy Project Manager to Admin migration impact without changing accounts, grants, owners or history.'

    def add_arguments(self,parser):
        parser.add_argument('--database',default='default')

    def handle(self,*args,**options):
        migration=importlib.import_module('core.migrations.0051_consolidate_project_manager_admin')
        self.stdout.write(json.dumps(migration.migration_impact(apps,options['database']),sort_keys=True,indent=2))
