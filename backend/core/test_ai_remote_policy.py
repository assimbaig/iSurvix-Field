"""A legacy PC worker cannot silently bypass a company's configured AI policy."""
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from .test_remote_survey_worker import Fixtures, SETTINGS
from . import remote_worker_service as bridge


@override_settings(**SETTINGS)
class RemoteProviderPolicyTests(Fixtures, TestCase):
    def enable_policy(self):
        from .ai_processing_models import AIProcessingSettings
        return AIProcessingSettings.objects.create(company=self.company, enabled=True)

    def test_configured_job_stays_queued_without_uncontrolled_pc_inference(self):
        self.enable_policy()
        self.assertIsNone(bridge.claim(self.credential, self.identity))
        job = self.revision.processing_job
        job.refresh_from_db()
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.attempts, 0)
        self.assertIn('configured AI policy', job.error)

    def test_enabling_policy_preserves_an_existing_native_pinned_lease(self):
        claimed = bridge.claim(self.credential, self.identity)
        job=self.revision.processing_job
        job.refresh_from_db()
        native_pin=job.model_digest
        self.enable_policy()
        task=bridge.next_task(self.credential, claimed['job_id'], claimed['lease'])
        self.assertEqual(task['kind'],'source')
        job.refresh_from_db()
        self.assertEqual(job.model_digest,native_pin)
        from .ai_processing_models import AIProcessingPolicy
        self.assertFalse(AIProcessingPolicy.objects.filter(job=job).exists())
        self.assertFalse(self.revision.source_analyses.exists())

    def test_disabling_unpinned_configuration_preserves_legacy_pc_path(self):
        config = self.enable_policy()
        config.enabled = False
        config.save()
        self.assertIsNotNone(bridge.claim(self.credential, self.identity))
