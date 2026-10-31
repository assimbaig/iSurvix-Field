"""Customer-server browser dependencies must work without contacting a CDN."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import build_opener, ProxyHandler

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.template.loader import render_to_string
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse


class BrowserResources(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.urls = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in ('script', 'img', 'iframe') and attrs.get('src'):
            self.urls.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') in ('stylesheet', 'preconnect', 'preload'):
            self.urls.append(attrs.get('href', ''))


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
                   SECURE_SSL_REDIRECT=False)
class CustomerOfflinePageTests(TestCase):
    def setUp(self):
        from .test_role_designs import RoleDesignTests
        RoleDesignTests.setUp(self)

    def assert_local_resources(self, response):
        self.assertEqual(response.status_code, 200)
        urls = BrowserResources(response.content.decode()).urls
        self.assertTrue(urls, 'A successful offline page must still load its real styles and controls.')
        remote = [url for url in urls if urlsplit(url).netloc or urlsplit(url).scheme in ('http', 'https')]
        self.assertEqual(remote, [], 'Opening an operational page must not initiate external asset requests.')

    def test_sign_in_has_no_automatic_internet_dependencies(self):
        self.assert_local_resources(self.client.get(reverse('login')))

    def test_saved_role_workspaces_have_no_automatic_internet_dependencies(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            with self.subTest(role=role):
                self.assert_local_resources(self.client.get(reverse('governance_home'), follow=True))
                self.assert_local_resources(self.client.get(reverse('work_profile')))


class CustomerOfflineAssetTests(SimpleTestCase):
    def test_vendor_inventory_covers_real_bytes_and_license_notices(self):
        root = Path(__file__).resolve().parents[1] / 'static' / 'vendor'
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'], 1)
        self.assertTrue(manifest['assets'])
        for item in manifest['assets']:
            with self.subTest(path=item['path']):
                path = root / item['path']
                self.assertTrue(path.resolve().is_relative_to(root.resolve()))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])
                self.assertTrue((root / item['license_path']).is_file())
                self.assertTrue(item['source'].startswith('https://'))

    def test_vendor_stylesheets_resolve_fonts_and_images_locally(self):
        root = Path(__file__).resolve().parents[1] / 'static' / 'vendor'
        styles = list(root.rglob('*.css'))
        self.assertTrue(styles)
        for css in styles:
            for raw in re.findall(r'url\(([^)]+)\)', css.read_text(encoding='utf-8')):
                url = raw.strip(' \t\r\n\'"')
                if url.startswith(('data:', '#')):
                    continue
                with self.subTest(style=css.name, resource=url):
                    self.assertFalse(urlsplit(url).netloc)
                    self.assertTrue((css.parent / urlsplit(url).path).is_file())

    def test_saved_coordinate_map_requires_explicit_online_basemap_action(self):
        html = render_to_string('dashboards/_geolocation_tab.html', {'locations': []})
        self.assertIn('id="load-online-basemap"', html)
        self.assertIn('Saved coordinates are available offline', html)
        self.assertNotIn('var currentLayer = tileLayers.voyager.addTo(geoMap)', html)


@override_settings(ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
                   SECURE_SSL_REDIRECT=False)
class CustomerOfflineHTTPTests(StaticLiveServerTestCase):
    host = '127.0.0.1'
    def test_real_http_sign_in_delivers_styles_and_scripts_from_same_server(self):
        opener = build_opener(ProxyHandler({}))
        with opener.open(self.live_server_url + reverse('login'), timeout=10) as response:
            html = response.read().decode()
        urls = BrowserResources(html).urls
        self.assertFalse([url for url in urls if urlsplit(url).netloc])
        self.assertTrue(any('bootstrap' in url for url in urls))
        for url in urls:
            if not url.startswith('/static/'):
                continue
            with self.subTest(resource=url), opener.open(self.live_server_url + url, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 0)
