"""Activation and daily-schedule controls, loaded in clean settings processes."""
import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase


class WorkflowEmailConfigurationTests(SimpleTestCase):
    def settings(self, **overrides):
        env = {key: value for key, value in os.environ.items()
               if key not in ('ISURVIX_NOTIFICATION_EMAIL_ENABLED',
                              'ISURVIX_WORKFLOW_NOTIFICATION_EMAIL_ENABLED',
                              'ISURVIX_WORKFLOW_EMAIL_DAILY_ENABLED',
                              'ISURVIX_WORKFLOW_EMAIL_DAILY_HOUR_UTC')}
        env.update(overrides)
        script = """import json,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1]).parents[1]))
value=runpy.run_path(sys.argv[1])
print(json.dumps({key:value[key] for key in ('WORKFLOW_NOTIFICATION_EMAIL_ENABLED','WORKFLOW_EMAIL_DAILY_ENABLED','WORKFLOW_EMAIL_DAILY_HOUR')}))
"""
        return subprocess.run([sys.executable, '-c', script,
                               str(Path(__file__).resolve().parents[1] / 'checklist/settings.py')],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_disabled_mail_cannot_be_overridden_by_workflow_flag(self):
        result = self.settings(ISURVIX_WORKFLOW_NOTIFICATION_EMAIL_ENABLED='True')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['WORKFLOW_NOTIFICATION_EMAIL_ENABLED'])

    def test_common_activation_includes_workflow_notifications(self):
        result = self.settings(ISURVIX_NOTIFICATION_EMAIL_ENABLED='True')
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value['WORKFLOW_NOTIFICATION_EMAIL_ENABLED'])
        self.assertTrue(value['WORKFLOW_EMAIL_DAILY_ENABLED'])
        self.assertEqual(value['WORKFLOW_EMAIL_DAILY_HOUR'], 15)

    def test_operator_can_disable_workflow_or_daily_summary(self):
        result = self.settings(ISURVIX_NOTIFICATION_EMAIL_ENABLED='True',
                               ISURVIX_WORKFLOW_NOTIFICATION_EMAIL_ENABLED='False',
                               ISURVIX_WORKFLOW_EMAIL_DAILY_ENABLED='False')
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertFalse(value['WORKFLOW_NOTIFICATION_EMAIL_ENABLED'])
        self.assertFalse(value['WORKFLOW_EMAIL_DAILY_ENABLED'])

    def test_schedule_accepts_valid_utc_hour(self):
        result = self.settings(ISURVIX_WORKFLOW_EMAIL_DAILY_HOUR_UTC='23')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['WORKFLOW_EMAIL_DAILY_HOUR'], 23)

    def test_invalid_schedule_stops_with_clear_configuration_error(self):
        for hour in ('-1', '24', '18.5', 'later'):
            with self.subTest(hour=hour):
                result = self.settings(ISURVIX_WORKFLOW_EMAIL_DAILY_HOUR_UTC=hour)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ISURVIX_WORKFLOW_EMAIL_DAILY_HOUR_UTC must be an integer from 0 to 23',
                              result.stderr)
