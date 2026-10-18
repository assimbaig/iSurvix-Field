"""Command-level recovery from transient SQLite contention."""
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.db import OperationalError
from django.test import SimpleTestCase,override_settings

@override_settings(LOCAL_AI_ENABLED=True)
class PhotoWorkerCommandTests(SimpleTestCase):
    @patch('core.management.commands.photo_worker.close_old_connections')
    @patch('core.management.commands.photo_worker.time.sleep')
    @patch('core.management.commands.photo_worker.process_next')
    def test_locked_database_retries_next_iteration_without_losing_consumer(self,process,sleep,close):
        process.side_effect=[OperationalError('database is locked'),False,KeyboardInterrupt()]
        output=StringIO()
        call_command('photo_worker',stdout=output)
        self.assertEqual(process.call_count,3)
        self.assertEqual(sleep.call_count,2)
        close.assert_called_once_with()
        self.assertIn('Worker stopped',output.getvalue())

    @patch('core.management.commands.photo_worker.close_old_connections')
    @patch('core.management.commands.photo_worker.time.sleep')
    @patch('core.management.commands.photo_worker.process_next')
    def test_unrelated_database_errors_are_not_silenced(self,process,sleep,close):
        process.side_effect=OperationalError('no such table: core_photojob')
        with self.assertRaises(OperationalError):
            call_command('photo_worker',stdout=StringIO())
        close.assert_not_called()
        sleep.assert_not_called()

    @patch('core.management.commands.photo_worker.close_old_connections')
    @patch('core.management.commands.photo_worker.time.sleep')
    @patch('core.management.commands.photo_worker.process_next')
    def test_once_returns_after_busy_attempt_without_background_loop(self,process,sleep,close):
        process.side_effect=OperationalError('database table is locked: core_photojob')
        call_command('photo_worker',once=True,stdout=StringIO())
        self.assertEqual(process.call_count,1)
        close.assert_called_once_with()
        sleep.assert_not_called()
