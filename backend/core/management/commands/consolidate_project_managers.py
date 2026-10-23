"""Explicit retry for accounts deferred by the initial identity migration."""
import importlib
import json
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connections,transaction


class Command(BaseCommand):
    help='Default: report only. --apply retries reviewed legacy PM identities; unresolved bindings remain deferred.'

    def add_arguments(self,parser):
        parser.add_argument('--database',default='default')
        parser.add_argument('--apply',action='store_true',help='Apply the reported transition after binding review and a verified backup of real/shared data.')

    def handle(self,*args,**options):
        migration=importlib.import_module('core.migrations.0051_consolidate_project_manager_admin')
        alias=options['database']
        if options['apply']:
            with transaction.atomic(using=alias):
                migration.consolidate_project_managers(apps,connections[alias].schema_editor())
        self.stdout.write(json.dumps(migration.migration_impact(apps,alias),sort_keys=True,indent=2))
