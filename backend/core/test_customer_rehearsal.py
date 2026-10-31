"""Keep the disposable installer rehearsal connected to real Django routes."""
from pathlib import Path
import re

from django.test import SimpleTestCase
from django.urls import resolve


class CustomerRehearsalRouteTests(SimpleTestCase):
    def test_rehearsal_probes_use_registered_application_routes(self):
        script = (Path(__file__).resolve().parents[2] / 'deploy/verify_customer.sh').read_text(encoding='utf-8')
        paths = set(re.findall(r"https://customer\.example\.test:8443(/[^'\"\s]*)", script))
        paths.update(re.findall(r"base\+'([^']+)'", script))
        # The raw-media probe is deliberately denied by Nginx, not Django.
        routes = {path for path in paths if not path.startswith('/media/')}
        self.assertGreaterEqual(len(routes), 3, 'Readiness, login and authenticated status must be exercised.')
        for path in sorted(routes):
            with self.subTest(path=path):
                resolve(path)
