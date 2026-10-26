"""Top evidence filters retain controls and role behavior without touching review data."""
from html.parser import HTMLParser
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import test_engineer_category_submission_acceptance as fixture


class ToolbarMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'ancestors': list(self.stack)}
        self.nodes.append(node)
        if tag not in {'input', 'img', 'meta', 'link', 'br', 'hr', 'source', 'area', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]['tag'] == tag:
                del self.stack[index:]
                break

    def by_id(self, value):
        matches = [n for n in self.nodes if n['attrs'].get('id') == value]
        if len(matches) != 1:
            raise AssertionError(f'Expected one {value}, found {len(matches)}')
        return matches[0]

    def filterbar(self):
        matches = [n for n in self.nodes if 'qa-evidence-filterbar' in n['attrs'].get('class', '').split()]
        if len(matches) != 1:
            raise AssertionError(f'Expected one compact top filter bar, found {len(matches)}')
        return matches[0]


class EvidenceFilterToolbarUnitTests(SimpleTestCase):
    def render_workspace(self, quick=True, role='QUALITY_ENGINEER'):
        return render_to_string('dashboards/qa_evidence_review.html', {
            'checklist': SimpleNamespace(pk=7, site_id='SYNTHETIC-SITE', project=SimpleNamespace(name='Synthetic project')),
            'request': SimpleNamespace(user=SimpleNamespace(pk=9, profile=SimpleNamespace(role=role))),
            'qa_quick_review': quick, 'evidence_review_role': role,
        })

    def assert_top_filters(self, html, quick=True):
        tree = ToolbarMarkup(html)
        bar = tree.filterbar()
        wrappers = [n for n in tree.nodes if 'qa-view-tools' in n['attrs'].get('class', '').split()]
        self.assertEqual(len(wrappers), 1, 'One shared fixed review-controls wrapper is required')
        wrapper = wrappers[0]
        self.assertEqual(wrapper['ancestors'][-1]['attrs'].get('id'), 'qa-photo-evidence-view')
        self.assertIs(bar['ancestors'][-1], wrapper)
        self.assertIn('aria-label', bar['attrs'])
        heading = tree.by_id('qa-item-title')
        self.assertLess(tree.nodes.index(bar), tree.nodes.index(heading))
        action = tree.by_id('qa-assign-selected')
        self.assertIn(wrapper, action['ancestors'])
        self.assertIn(wrapper, heading['ancestors'])
        self.assertLess(tree.nodes.index(bar), tree.nodes.index(action))
        self.assertLess(tree.nodes.index(action), tree.nodes.index(heading))
        self.assertTrue(any(a['attrs'].get('id') == 'qa-photo-evidence-view' for a in heading['ancestors']))
        controls = ['qa-photo-view'] + (['qa-photo-status', 'qa-photo-search', 'qa-thumbnail-size'] if quick else [])
        for control in controls:
            self.assertIn(bar, tree.by_id(control)['ancestors'], control)
        # Action identity stays separate so filtering is not an accidental assignment.
        self.assertNotIn(bar, tree.by_id('qa-assign-selected')['ancestors'])
        return tree

    def test_quick_qa_filters_are_in_a_single_top_bar_with_existing_action_ids(self):
        self.assert_top_filters(self.render_workspace())

    def test_team_lead_and_nonquick_shared_workspace_keep_their_filter_contract(self):
        self.assert_top_filters(self.render_workspace(role='TEAM_LEAD'))
        self.assert_top_filters(self.render_workspace(quick=False, role='ADMIN'), quick=False)


@override_settings(SECRET_KEY='isolated-filter-toolbar', ROOT_URLCONF='checklist.urls_local',
                   ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EvidenceFilterToolbarIntegrationTests(TestCase):
    setUp = fixture.EngineerCategorySubmissionAcceptanceTests.setUp
    person = fixture.EngineerCategorySubmissionAcceptanceTests.person
    add_photo = fixture.EngineerCategorySubmissionAcceptanceTests.add_photo
    raw = fixture.EngineerCategorySubmissionAcceptanceTests.raw
    post = fixture.EngineerCategorySubmissionAcceptanceTests.post
    upload = fixture.EngineerCategorySubmissionAcceptanceTests.upload
    state = fixture.EngineerCategorySubmissionAcceptanceTests.state
    submit = fixture.EngineerCategorySubmissionAcceptanceTests.submit

    def test_saved_qa_workspace_renders_top_filters_without_mutating_submission(self):
        self.upload('Civil')
        response, _ = self.submit()
        self.assertEqual(response.status_code, 201)
        revision = self.checklist.processing_revisions.get()
        before = revision.snapshot
        self.client.force_login(self.quality)
        response = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        EvidenceFilterToolbarUnitTests().assert_top_filters(response.content.decode())
        revision.refresh_from_db()
        self.assertEqual(revision.snapshot, before)

    def test_engineer_still_gets_category_upload_screen_without_qa_matching_filters(self):
        self.client.force_login(self.engineer)
        response = self.client.get(reverse('photo_workspace', args=[self.checklist.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('id="qa-photo-status"', html)
        self.assertNotIn('id="qa-assignment-target"', html)
