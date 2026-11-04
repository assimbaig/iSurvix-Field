"""Offline checks for the published corporate-page partial update.

Only public source and public-HTML invariants are used. No database, account,
network service, browser profile, credential or model is accessed.
"""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import re
import unittest

BASE = Path(__file__).resolve().parents[1]
LOGIN = 'https://app.isurvix.com/login/'
FILES = {
    'index.html', 'platform-login-v4.css', 'platform-login.js', 'ifield.html',
    'ifield-info.css', 'products.html', 'solutions.html', 'isurvix-survey.html',
}


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


def segment(tag, source):
    return re.search(rf'<{tag}\b.*?</{tag}>', source, re.S).group()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class PublicWebsiteTests(unittest.TestCase):
    maxDiff = 800

    @classmethod
    def setUpClass(cls):
        cls.pages = {name: (BASE / name).read_text(encoding='utf-8')
                     for name in FILES if name.endswith('.html')}
        cls.home = cls.pages['index.html']
        cls.product = cls.pages['ifield.html']
        cls.invariants = json.loads((BASE / 'tests/public-page-invariants.json').read_text())

    def test_publication_manifest_lists_only_eight_public_files_with_exact_bytes(self):
        manifest = json.loads((BASE / 'source-manifest.json').read_text())
        self.assertEqual(manifest['format'], 'isurvix-corporate-partial-v1')
        self.assertEqual({item['path'] for item in manifest['files']}, FILES)
        self.assertEqual(len(manifest['files']), len(FILES))
        for item in manifest['files']:
            source = BASE / item['path']
            self.assertEqual(source.parent, BASE)
            self.assertEqual(source.stat().st_size, item['bytes'])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), item['sha256'])

    def test_homepage_is_the_only_corporate_sign_in_entry(self):
        for name, source in self.pages.items():
            entries = [attributes for tag, attributes in Document(source).tags
                       if tag == 'a' and '/login/' in attributes.get('href', '')]
            self.assertEqual(len(entries), 1 if name == 'index.html' else 0, name)
            if entries:
                self.assertEqual(entries[0]['href'], LOGIN)
                self.assertFalse(entries[0].get('target'))

    def test_native_disclosure_reuses_dark_contact_pill_and_complete_accessible_name(self):
        header = segment('header', self.home)
        summaries = [attributes for tag, attributes in Document(header).tags if tag == 'summary']
        self.assertEqual(len(summaries), 1)
        self.assertIn('nav-contact', summaries[0].get('class', '').split())
        self.assertEqual(summaries[0].get('aria-label'), 'Login to iSurvix Platform')
        self.assertEqual(summaries[0].get('aria-controls'), 'platform-login-options')
        self.assertIn('class="platform-login-label" aria-hidden="true">Login</span>', header)
        self.assertNotIn('Let\u2019s talk', header)
        self.assertLess(header.index('class="brand"'), header.index('id="navigation"'))
        self.assertLess(header.index('id="navigation"'), header.index('class="platform-login"'))

    def test_header_keeps_existing_navigation_and_branding(self):
        header = segment('header', self.home)
        for target in ['solutions.html', 'engineering.html', 'portfolio.html', 'clients.html', 'company.html']:
            self.assertIn(f'href="{target}"', header)
        self.assertIn('isurvix-logo-approved.png', header)

    def test_homepage_only_loads_versioned_platform_assets(self):
        for name, source in self.pages.items():
            if name == 'index.html':
                self.assertIn('href="platform-login-v4.css"', source)
                self.assertIn('src="platform-login.js"', source)
                self.assertNotIn('href="platform-login.css"', source)
            else:
                self.assertNotIn('platform-login-v4.css', source)
                self.assertNotIn('platform-login.js', source)

    def test_future_platforms_are_explicitly_unavailable_without_fake_login_links(self):
        panel = re.search(r'<div id="platform-login-options".*?</details>', self.home, re.S).group()
        self.assertEqual(panel.count('class="platform-login-unavailable"'), 3)
        self.assertEqual(panel.count('Coming soon'), 3)
        for platform in ['iGeoView', 'iMoneta', 'Engineering Intelligence']:
            self.assertIn(platform, panel)
        links = [attributes.get('href') for tag, attributes in Document(panel).tags if tag == 'a']
        self.assertEqual(links, [LOGIN])

    def test_public_pages_do_not_collect_credentials_or_embed_the_private_app(self):
        for name, source in self.pages.items():
            self.assertFalse([tag for tag, _ in Document(source).tags if tag in ['form', 'input', 'iframe']], name)
            self.assertNotRegex(source, r'-----BEGIN (?:OPENSSH|RSA|EC|PRIVATE)')
        script = (BASE / 'platform-login.js').read_text(encoding='utf-8')
        self.assertNotRegex(script, r'localStorage|sessionStorage|innerHTML|location\.search|window\.location|fetch\(')

    def test_product_explains_current_workflow_without_calling_ifield_coming_soon(self):
        self.assertNotIn('Coming Soon', self.product)
        for term in ['Private beta', 'For field engineers', 'For reviewers', 'For companies',
                     'Engineer', 'QA', 'Team Lead', 'Client', 'invitation', 'Human decisions']:
            self.assertIn(term, self.product)

    def test_real_demo_glimpses_and_planned_housing_are_separate(self):
        figures = [attributes for tag, attributes in Document(self.product).tags if tag == 'figure']
        self.assertEqual(sum(figure.get('data-preview-kind') == 'screenshot' for figure in figures), 3)
        self.assertEqual(sum(figure.get('data-preview-kind') == 'concept' for figure in figures), 2)
        self.assertIn('Field screenshots contain demo data.', self.product)
        self.assertIn('not evidence of a released housing inspection module', self.product)

    def test_legacy_product_alias_keeps_current_content_and_canonical(self):
        self.assertEqual((BASE / 'isurvix-survey.html').read_bytes(), (BASE / 'ifield.html').read_bytes())
        self.assertIn('<link rel="canonical" href="https://isurvix.com/ifield.html">', self.product)

    def test_catalog_ifield_cards_are_current_without_changing_unrelated_copy(self):
        for name in ['products.html', 'solutions.html']:
            source = self.pages[name]
            cards = [card for card in re.findall(r'<article\b.*?</article>', source, re.S)
                     if '<h3>iField</h3>' in card]
            self.assertEqual(len(cards), 1)
            self.assertNotIn('Coming Soon', cards[0])
            self.assertIn('Available', cards[0])
            self.assertIn('Private beta', cards[0])
            self.assertIn('PRODUCT CONCEPT OVERVIEW', cards[0])
            self.assertEqual(digest(source.replace(cards[0], '<IFIELD_ARTICLE>', 1)),
                             self.invariants['catalog_outside_ifield_article_sha256'][name])

    def test_existing_homepage_body_product_header_and_footers_are_preserved(self):
        self.assertEqual(digest(segment('main', self.home)), self.invariants['homepage_main_sha256'])
        self.assertEqual(digest(segment('footer', self.home)), self.invariants['homepage_footer_sha256'])
        self.assertEqual(digest(segment('header', self.product)), self.invariants['ifield_header_sha256'])
        self.assertEqual(digest(segment('footer', self.product)), self.invariants['ifield_footer_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
