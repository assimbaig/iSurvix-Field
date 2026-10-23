"""Ordinary ORM event immutability, including supported SET_NULL lifecycle."""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from unittest.mock import patch

from .models import GovernanceAudit, Project


class GovernanceAuditIntegrityTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user('audit-integrity-actor')
        self.project = Project.objects.create(name='Audit integrity fixture')
        self.event = GovernanceAudit.objects.create(
            action='fixture_recorded', actor=self.actor,
            actor_name='Original actor snapshot', project=self.project,
            details={'source_hash': 'a' * 64},
        )

    def unchanged(self):
        saved = GovernanceAudit.objects.get(pk=self.event.pk)
        self.assertEqual(saved.action, 'fixture_recorded')
        self.assertEqual(saved.actor_name, 'Original actor snapshot')
        self.assertEqual(saved.details, {'source_hash': 'a' * 64})

    def test_instance_save_and_delete_cannot_rewrite_or_remove_event(self):
        self.event.action = 'rewritten'
        with self.assertRaises(ValidationError):
            self.event.save()
        with self.assertRaises(ValidationError):
            self.event.delete()
        self.unchanged()

    def test_queryset_bulk_and_base_manager_updates_are_guarded(self):
        for manager in (GovernanceAudit.objects, GovernanceAudit._base_manager):
            with self.subTest(manager=repr(manager)):
                with self.assertRaises(ValidationError):
                    manager.filter(pk=self.event.pk).update(details={})
                with self.assertRaises(ValidationError):
                    manager.filter(pk=self.event.pk).delete()
        self.event.action = 'rewritten'
        with self.assertRaises(ValidationError):
            GovernanceAudit.objects.bulk_update([self.event], ['action'])
        self.unchanged()

    def test_forged_new_instance_and_upserts_cannot_replace_existing_event(self):
        replacement = GovernanceAudit(pk=self.event.pk, action='rewritten', details={})
        with self.assertRaises(ValidationError):
            replacement.save()
        with self.assertRaises(ValidationError):
            GovernanceAudit.objects.bulk_create(
                [replacement], update_conflicts=True,
                update_fields=['action'], unique_fields=['id'],
            )
        with self.assertRaises(ValidationError):
            GovernanceAudit.objects.bulk_create(
                [replacement], None, False, True, ['action'], ['id'],
            )
        self.unchanged()

    def test_append_and_bulk_append_remain_available(self):
        GovernanceAudit.objects.create(action='next_event')
        GovernanceAudit.objects.bulk_create([
            GovernanceAudit(action='bulk_first'), GovernanceAudit(action='bulk_second'),
        ])
        self.assertEqual(GovernanceAudit.objects.count(), 4)
        self.unchanged()

    def test_new_save_always_inserts_and_refuses_explicit_update_options(self):
        with patch('django.db.models.Model.save') as save:
            GovernanceAudit(pk=999999, action='fresh').save()
        self.assertTrue(save.call_args.kwargs['force_insert'])
        with self.assertRaises(ValidationError):
            GovernanceAudit(action='fresh').save(force_update=True)
        with self.assertRaises(ValidationError):
            GovernanceAudit(action='fresh').save(update_fields=['action'])

    def test_actor_and_project_deletion_preserve_event_snapshot(self):
        self.actor.delete()
        self.project.delete()
        saved = GovernanceAudit.objects.get(pk=self.event.pk)
        self.assertIsNone(saved.actor_id)
        self.assertIsNone(saved.project_id)
        self.unchanged()

    def test_lifecycle_exception_cannot_reassign_an_existing_reference(self):
        other = User.objects.create_user('audit-integrity-other')
        with self.assertRaises(ValidationError):
            GovernanceAudit.objects.filter(pk=self.event.pk).update(actor=other)
        with self.assertRaises(ValidationError):
            GovernanceAudit.objects.filter(pk=self.event.pk).update(actor_name='Changed snapshot')
        self.unchanged()
