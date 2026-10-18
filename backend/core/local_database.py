"""Configure the local SQLite file before starting web and worker processes."""
import sqlite3
from contextlib import closing
from pathlib import Path


def enable_wal(path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # journal_mode is persistent; set once at startup, not on every connection.
    # Never replace/restore/delete a database or any of its WAL sidecar files.
    with closing(sqlite3.connect(path,timeout=30,isolation_level=None)) as database:
        mode=database.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        if mode.lower()!='wal':
            raise RuntimeError('Local SQLite could not enable WAL; stop existing app processes and retry.')
    return mode
