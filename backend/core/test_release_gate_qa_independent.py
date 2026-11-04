"""Independent same-source release provenance attacks; synthetic CI records only."""
from copy import deepcopy
from itertools import permutations
from unittest.mock import patch

from django.test import SimpleTestCase

from . import test_release_gate as fixtures


class IndependentReleaseGateReviewTests(SimpleTestCase):
    def setUp(self):
        self.gate = fixtures.module()
        self.runs = [dict(id=number, run_number=number, run_attempt=1,
            path=path, head_sha=fixtures.SHA,
            head_repository={'full_name': fixtures.REPO}, event='pull_request',
            status='completed', conclusion='success', updated_at='2026-11-04T10:00:00Z')
            for number, path in enumerate(self.gate.REQUIRED_WORKFLOWS, 1)]

    def verify(self, records):
        return self.gate.verified_runs([*records, *self.runs[1:]], fixtures.SHA, fixtures.REPO)

    def test_independent_pending_or_failed_run_cannot_hide_behind_newer_push_success(self):
        push = {**self.runs[0], 'id': 100, 'run_number': 100, 'event': 'push',
                'updated_at': '2026-11-04T12:00:00Z'}
        for status, conclusion in [('in_progress', None), ('completed', 'failure')]:
            independent = {**self.runs[0], 'id': 101, 'run_number': 101,
                           'status': status, 'conclusion': conclusion}
            for records in permutations([push, independent]):
                with self.subTest(status=status, first=records[0]['id']), self.assertRaises(ValueError):
                    self.verify(records)

    def test_terminal_conclusions_of_same_attempt_cannot_change_with_a_later_timestamp(self):
        failed = {**self.runs[0], 'conclusion': 'failure'}
        changed_success = {**self.runs[0], 'updated_at': '2026-11-04T11:00:00Z'}
        for records in permutations([failed, changed_success]):
            with self.subTest(first=records[0]['conclusion']), self.assertRaises(ValueError):
                self.verify(records)

    def test_legitimate_progress_and_new_attempt_remain_compatible(self):
        progress = {**self.runs[0], 'status': 'in_progress', 'conclusion': None,
                    'updated_at': '2026-11-04T09:00:00Z'}
        for records in permutations([progress, self.runs[0]]):
            result = self.verify(records)
            self.assertEqual(set(result), set(self.gate.REQUIRED_WORKFLOWS))
            self.assertEqual(result[self.gate.REQUIRED_WORKFLOWS[0]]['run_attempt'], 1)
        failed = {**self.runs[0], 'conclusion': 'failure',
                  'updated_at': '2026-11-04T12:00:00Z'}
        retried = {**self.runs[0], 'run_attempt': 2}
        for records in permutations([failed, retried]):
            result = self.verify(records)
            self.assertEqual(result[self.gate.REQUIRED_WORKFLOWS[0]]['run_attempt'], 2)
            self.assertEqual(result[self.gate.REQUIRED_WORKFLOWS[0]]['source_commit'], fixtures.SHA)

    def test_required_record_provenance_has_strict_types_and_consistent_identity(self):
        for key, value in [('id', True), ('id', 0), ('run_attempt', '2'),
                           ('run_number', -1), ('updated_at', None),
                           ('updated_at', '2026-11-04T10:00:00'),
                           ('updated_at', '2026-11-04T10:00:00+25:00')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.verify([{**self.runs[0], key: value}])
        with self.assertRaises(ValueError):
            self.verify([self.runs[0], {**self.runs[0], 'run_number': 99}])

    def test_one_run_identity_cannot_prove_multiple_required_workflows(self):
        # A workflow-run URL identifies one run with one immutable workflow path.
        # Repeating that identity under another path must not satisfy two gates.
        forged = deepcopy(self.runs)
        forged[1]['id'] = forged[0]['id']
        for records in (forged, list(reversed(forged))):
            with self.assertRaises(ValueError):
                self.gate.verified_runs(records, fixtures.SHA, fixtures.REPO)
        persisted = self.gate.verified_runs(self.runs, fixtures.SHA, fixtures.REPO)
        repeated_id = persisted[self.gate.REQUIRED_WORKFLOWS[0]]['run_id']
        repeated_url = persisted[self.gate.REQUIRED_WORKFLOWS[0]]['url']
        for check in persisted.values():
            check['run_id'] = repeated_id
            check['url'] = repeated_url
        with self.assertRaises(ValueError):
            self.gate._checks(persisted, fixtures.SHA)

    def test_later_page_independent_failure_blocks_even_with_identical_success_duplicates(self):
        unrelated = [{**self.runs[0], 'id': 1000 + i,
                      'path': '.github/workflows/unrelated.yml'} for i in range(97)]
        page1 = {'workflow_runs': [*self.runs, *unrelated]}
        page2 = {'workflow_runs': [deepcopy(self.runs[0]),
            {**self.runs[0], 'id': 500, 'run_number': 500,
             'conclusion': 'failure', 'updated_at': '2026-11-04T09:00:00Z'}]}
        with patch.object(self.gate, '_api', side_effect=[page1, page2]) as transport:
            with self.assertRaises(ValueError):
                self.gate.fetch_verified(fixtures.REPO, fixtures.SHA, 'synthetic-read-only-token')
        self.assertEqual(transport.call_count, 2)
        self.assertIn('page=2', transport.call_args_list[1].args[0])

    def test_pagination_limit_and_malformed_page_do_not_accept_partial_success(self):
        for payload in [{'workflow_runs': None}, {'workflow_runs': {}}, []]:
            with self.subTest(payload=payload), patch.object(self.gate, '_api', return_value=payload):
                with self.assertRaises(ValueError):
                    self.gate.fetch_verified(fixtures.REPO, fixtures.SHA, 'synthetic-read-only-token')
        full = {'workflow_runs': [*self.runs, *[
            {**self.runs[0], 'id': 1000 + i, 'path': '.github/workflows/unrelated.yml'}
            for i in range(97)]]}
        with patch.object(self.gate, '_api', return_value=full) as transport:
            with self.assertRaises(ValueError):
                self.gate.fetch_verified(fixtures.REPO, fixtures.SHA, 'synthetic-read-only-token')
        self.assertEqual(transport.call_count, 10)
