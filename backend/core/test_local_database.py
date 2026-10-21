"""File-backed WAL contention and idle queue regression checks."""
import sqlite3
from contextlib import closing
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase
from .local_database import enable_wal

class LocalDatabaseConcurrencyTests(SimpleTestCase):
    def test_wal_preserves_existing_rows_allows_readers_and_serializes_writers(self):
        temporary_root=Path(__file__).resolve().parents[2]/'.local'/'tmp'
        temporary_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root,prefix='wal-regression-') as temporary:
            path=Path(temporary)/'survey.sqlite3'
            with closing(sqlite3.connect(path)) as original:
                original.execute('CREATE TABLE evidence(id INTEGER PRIMARY KEY,value TEXT)')
                original.execute("INSERT INTO evidence VALUES(1,'preserved')")
                original.commit()
            self.assertEqual(enable_wal(path),'wal')
            # Match enable_wal/settings_local's bounded 30-second busy timeout.
            # A three-second fixture timeout tested host scheduling/I/O stalls
            # rather than the application's actual serialized-writer behavior.
            lock_timeout=30
            first=sqlite3.connect(path,timeout=lock_timeout,isolation_level=None)
            reader=None
            thread=None
            try:
                reader=sqlite3.connect(path,timeout=lock_timeout,isolation_level=None)
                first.execute('BEGIN IMMEDIATE')
                first.execute("UPDATE evidence SET value='first' WHERE id=1")
                # A web/session reader still sees the last committed state.
                self.assertEqual(reader.execute('SELECT value FROM evidence').fetchone()[0],'preserved')
                waiting=threading.Event()
                entered=threading.Event()
                errors=[]
                def second_writer():
                    try:
                        with closing(sqlite3.connect(path,timeout=lock_timeout,isolation_level=None)) as second:
                            waiting.set()
                            second.execute('BEGIN IMMEDIATE')
                            entered.set()
                            second.execute("UPDATE evidence SET value='second' WHERE id=1")
                            second.execute('COMMIT')
                    except Exception as exc:
                        errors.append(exc)
                thread=threading.Thread(target=second_writer)
                thread.start()
                self.assertTrue(waiting.wait(10))
                self.assertFalse(entered.wait(.05))
                first.execute('COMMIT')
                thread.join(timeout=lock_timeout+2)
                self.assertFalse(thread.is_alive())
                self.assertFalse(errors)
                self.assertTrue(entered.is_set())
                self.assertEqual(reader.execute('SELECT value FROM evidence').fetchone()[0],'second')
            finally:
                # Never mask a contention assertion with Windows file cleanup
                # errors, or leave a writer alive when its temporary DB is removed.
                if reader is not None:
                    reader.close()
                if first.in_transaction:
                    first.rollback()
                first.close()
                if thread is not None and thread.is_alive():
                    thread.join(timeout=lock_timeout+2)

class IdlePhotoWorkerTests(TestCase):
    def test_idle_poll_performs_no_lease_writes_or_background_thread(self):
        from .photo_queue import process_next
        with patch('core.photo_queue.inference_lease') as lease:
            with self.assertNumQueries(1):
                self.assertFalse(process_next())
            lease.assert_not_called()
