"""Meaningful isolated regression: links are not unique photos."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from counter import count_unique


class EvidenceCountTests(unittest.TestCase):
    def test_repeated_photo_ids_count_once(self):
        self.assertEqual(count_unique(['p1', 'p1', 'p2']), 2)

    def test_empty_and_distinct_photo_ids(self):
        self.assertEqual(count_unique([]), 0)
        self.assertEqual(count_unique(['p1', 'p2']), 2)
