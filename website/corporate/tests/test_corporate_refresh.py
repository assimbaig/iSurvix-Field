"""Independent public refresh contracts; read-only, no remote form submissions."""
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from threading import Thread
import unittest
from urllib.parse import urlsplit
from urllib.request import urlopen

BASE = Path(__file__).resolve().parents[1]


class Tags(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, name, attributes):
        self.tags.append((name, dict(attributes)))


class CorporateRefreshTests(unittest.TestCase):
    def test_platform_dropdown_has_three_accessible_logo_only_native_platform_links(self):
        source = (BASE / 'index.html').read_text(encoding='utf-8')
        panel = re.search(r'<div id="platform-login-options".*?</details>', source, re.S).group()
        links = [attrs for tag, attrs in Tags(panel).tags if tag == 'a']
        self.assertEqual(len(links), 3, 'All three existing platforms have usable login links')
        self.assertEqual({urlsplit(attrs['href']).hostname for attrs in links},
                         {'app.isurvix.com', 'www.imoneta.app', 'www.igeoview.app'})
        self.assertEqual({attrs['href'] for attrs in links},
                         {'https://app.isurvix.com/login/', 'https://www.imoneta.app/auth',
                          'https://www.igeoview.app/auth'})
        self.assertTrue(all(attrs.get('aria-label') and attrs.get('title') for attrs in links))
        for anchor in re.findall(r'<a\b.*?</a>', panel, re.S):
            tags = Tags(anchor).tags
            self.assertEqual(sum(tag == 'img' for tag, _ in tags), 1)
            self.assertTrue(all(attrs.get('alt') for tag, attrs in tags if tag == 'img'))
            self.assertEqual(re.sub(r'<[^>]*>', '', anchor).strip(), '', 'Logo links have no visible extra text')
        self.assertNotIn('Coming soon', panel)

    def test_homepage_has_specific_company_value_heading_not_only_generic_eyebrow(self):
        source = (BASE / 'index.html').read_text(encoding='utf-8')
        headings = re.findall(r'<h1\b[^>]*>(.*?)</h1>', source, re.S)
        self.assertEqual(len(headings), 1)
        text = re.sub(r'<[^>]+>', ' ', headings[0])
        self.assertIn('Engineering clarity.', text)
        self.assertIn('Connected fieldwork.', text)

    def test_primary_navigation_does_not_promote_unfinished_clients_page(self):
        for filename in ['index.html', 'ifield.html', 'products.html', 'solutions.html']:
            source = (BASE / filename).read_text(encoding='utf-8')
            header = re.search(r'<header\b.*?</header>', source, re.S).group()
            links = [attrs.get('href') for tag, attrs in Tags(header).tags if tag == 'a']
            self.assertNotIn('clients.html', links, filename)
            self.assertIn('company.html', links, filename)

    def test_public_pages_offer_privacy_information_without_collecting_passwords(self):
        for filename in ['index.html', 'ifield.html', 'products.html', 'solutions.html']:
            source = (BASE / filename).read_text(encoding='utf-8')
            footer = re.search(r'<footer\b.*?</footer>', source, re.S).group()
            self.assertIn('privacy.html', [attrs.get('href') for tag, attrs in Tags(footer).tags if tag == 'a'], filename)
            self.assertFalse([attrs for tag, attrs in Tags(source).tags
                              if tag == 'input' and attrs.get('type') == 'password'])

    def test_real_product_logo_assets_exist_and_have_accessible_labels(self):
        source = (BASE / 'products.html').read_text(encoding='utf-8')
        images = [attrs for tag, attrs in Tags(source).tags if tag == 'img']
        for name in ['ifield', 'igeoview', 'imoneta']:
            matches = [attrs for attrs in images if attrs.get('src') == f'assets/{name}-logo.webp']
            self.assertTrue(matches, f'{name} approved logo must be visible in product catalog')
            self.assertTrue(all(attrs.get('alt', '').strip() for attrs in matches))
            self.assertGreater((BASE / f'assets/{name}-logo.webp').stat().st_size, 100)

    def test_login_stays_homepage_only_and_points_to_existing_app(self):
        for filename in ['index.html', 'ifield.html', 'products.html', 'solutions.html', 'privacy.html']:
            source = (BASE / filename).read_text(encoding='utf-8')
            links = [attrs['href'] for tag, attrs in Tags(source).tags
                     if tag == 'a' and '/login/' in attrs.get('href', '')]
            self.assertEqual(links, ['https://app.isurvix.com/login/'] if filename == 'index.html' else [], filename)


class PublicPreviewIntegrationTests(unittest.TestCase):
    """Exercise linked public pages over a real isolated HTTP preview."""
    @classmethod
    def setUpClass(cls):
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(BASE)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_footer_privacy_journey_returns_actual_readable_public_page(self):
        with urlopen(self.origin + '/privacy.html', timeout=5) as response:
            self.assertEqual(response.status, 200)
            source = response.read().decode('utf-8')
        self.assertRegex(source, r'<h1\b[^>]*>.*?Privacy')
        self.assertIn('info@isurvix.com', source)
        self.assertIn('href="index.html"', source)
        self.assertNotIn('GDPR compliant', source)

    def test_current_ifield_and_catalog_do_not_send_visitors_to_future_release_copy(self):
        for filename in ['ifield.html', 'products.html', 'solutions.html', 'portfolio.html']:
            with self.subTest(filename=filename), urlopen(self.origin + '/' + filename, timeout=5) as response:
                self.assertEqual(response.status, 200)
                source = response.read().decode('utf-8')
                self.assertIn('Private beta', source)
                self.assertNotRegex(source, r'iField.{0,40}(?:Coming Soon|coming soon)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
