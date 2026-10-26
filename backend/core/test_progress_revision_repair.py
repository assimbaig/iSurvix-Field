"""R1: task membership cannot stand in for frozen submission membership."""
from copy import deepcopy
from types import SimpleNamespace

from django.http import Http404
from django.test import TestCase, override_settings

from . import test_qa_review_progress as fixtures


@override_settings(SECRET_KEY='isolated-frozen-photo-membership',
    ROOT_URLCONF='checklist.urls_local', ALLOWED_HOSTS=['testserver'],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProgressRevisionRepairTests(TestCase):
    setUp=fixtures.QAReviewProgressTests.setUp
    person=fixtures.QAReviewProgressTests.person
    add_photo=fixtures.QAReviewProgressTests.add_photo
    raw=fixtures.QAReviewProgressTests.raw
    post=fixtures.QAReviewProgressTests.post
    state=fixtures.QAReviewProgressTests.state
    upload=fixtures.QAReviewProgressTests.upload
    submit=fixtures.QAReviewProgressTests.submit
    assert_submitted=fixtures.QAReviewProgressTests.assert_submitted

    def test_same_task_photo_outside_frozen_revision_is_denied(self):
        from .qa_review_progress import progress
        original=deepcopy(self.revision.snapshot)
        outside=self.add_photo('purple')
        self.assertNotIn(outside.pk,[photo['id'] for photo in original['photos']])
        with self.assertRaises(Http404):
            progress(SimpleNamespace(user=self.quality,GET={'photo_id':str(outside.pk)}),self.checklist.pk)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.snapshot,original)
