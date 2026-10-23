"""Disposable migration histories; never reverse a populated shared test DB."""
import copy
import tempfile
from functools import wraps
from pathlib import Path
from django.db import connections


def isolated_migration_database(test):
    @wraps(test)
    def wrapped(*args,**kwargs):
        previous=connections['default']
        with tempfile.TemporaryDirectory(prefix='ifield-historical-migration-') as directory:
            config=copy.deepcopy(previous.settings_dict)
            config['NAME']=str(Path(directory)/'history.sqlite3')
            isolated=type(previous)(config,alias='default')
            connections['default']=isolated
            try:
                return test(*args,**kwargs)
            finally:
                isolated.close()
                connections['default']=previous
    return wrapped
