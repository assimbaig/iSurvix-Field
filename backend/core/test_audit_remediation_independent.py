"""Independent saved-data regressions for the approved 4 November audit repairs.

These exercise real HTTP/export/intake boundaries with isolated synthetic data.
They do not invoke a native model or certify production capacity.
"""
from datetime import timedelta
from io import BytesIO
from contextlib import ExitStack, contextmanager
import json
import os
import sys
from types import ModuleType
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from PIL import Image, XbmImagePlugin

from . import test_survey_processing as survey_fixture
from . import test_work_profiles as profile_fixture
from .models import (Checklist, Company, PhotoDraft, PhotoEvidence, PhotoJob,
                     Profile, Project, ProjectMembership)


@override_settings(SECRET_KEY="independent-audit-repair-synthetic",
    ROOT_URLCONF="checklist.urls_local", ALLOWED_HOSTS=["testserver"],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditRepairHTTPBoundaryTests(TestCase):
    setUp = survey_fixture.SurveyProcessingTests.setUp
    person = survey_fixture.SurveyProcessingTests.person
    add_photo = survey_fixture.SurveyProcessingTests.add_photo

    def browser(self, actor):
        browser = Client()
        browser.force_login(actor)
        return browser

    def test_private_state_prohibits_storage_for_each_internal_role(self):
        for actor in (self.engineer, self.quality, self.lead, self.admin):
            with self.subTest(role=actor.profile.role):
                response = self.browser(actor).get(reverse("photo_state", args=[self.checklist.pk]))
                self.assertEqual(response.status_code, 200)
                policy = response.headers.get("Cache-Control", "")
                self.assertIn("private", policy)
                self.assertIn("no-store", policy)

    def test_excel_revision_name_is_literal_after_actual_admin_publication(self):
        template = type(self.template).objects.create(
            name="Independent export draft", definition=self.schema, created_by=self.admin)
        browser = self.browser(self.admin)
        response = browser.post(reverse("checklist_template_edit", args=[template.pk]), {
            "action": "publish", "name": "=1+1", "definition": json.dumps(self.schema)})
        self.assertEqual(response.status_code, 302, response.content)
        template.refresh_from_db()
        self.assertTrue(template.published)
        survey = Checklist.objects.create(project=self.project, user=self.engineer,
            checklist_template=template, site_id="SYN-INDEPENDENT-EXPORT")
        response = browser.get(reverse("custom_checklist_download", args=[survey.pk]))
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content), data_only=False)
        try:
            cell = book.active["C6"]
            self.assertEqual(cell.data_type, "s", "Admin metadata must remain literal, never an Excel formula")
            self.assertIn("=1+1", cell.value)
        finally:
            book.close()

    def test_existing_session_loses_evidence_when_grant_is_revoked_or_actor_locked(self):
        for actor in (self.engineer, self.quality, self.lead, self.admin):
            browser = self.browser(actor)
            Profile.objects.filter(user=actor).update(is_locked=True)
            for name, args in (("photo_state", [self.checklist.pk]),
                               ("photo_evidence", [self.checklist.pk, self.photo.pk, "original"])):
                with self.subTest(role=actor.profile.role, state="locked", route=name):
                    reply = browser.get(reverse(name, args=args))
                    self.assertIn(reply.status_code, (302, 403, 404))
                    reply.close()
            Profile.objects.filter(user=actor).update(is_locked=False)
            ProjectMembership.objects.update_or_create(user=actor, project=self.project,
                defaults={"is_active": False})
            with self.subTest(role=actor.profile.role, state="revoked"):
                self.assertIn(browser.get(reverse("photo_state", args=[self.checklist.pk])).status_code,
                    (302, 403, 404))
            ProjectMembership.objects.filter(user=actor, project=self.project).delete()

    def test_foreign_company_cannot_read_or_export_even_with_local_photo_id(self):
        company = Company.objects.create(name="Independent foreign company")
        project = Project.objects.create(name="Independent foreign project", company=company)
        actor = self.person("foreign_independent", Profile.Roles.ADMIN, project)
        browser = self.browser(actor)
        for name, args in (("photo_state", [self.checklist.pk]),
                           ("photo_evidence", [self.checklist.pk, self.photo.pk, "original"]),
                           ("custom_checklist_download", [self.checklist.pk])):
            with self.subTest(route=name):
                response = browser.get(reverse(name, args=args))
                self.assertIn(response.status_code, (403, 404))
                response.close()

    def test_rejected_corrupt_batch_does_not_leave_the_valid_half_saved(self):
        data = BytesIO()
        Image.new("RGB", (31, 23), "orange").save(data, "PNG")
        before = PhotoEvidence.objects.count()
        response = self.browser(self.engineer).post(reverse("photo_upload", args=[self.checklist.pk]), {
            "group": "Civil", "files": [
                SimpleUploadedFile("valid.png", data.getvalue(), "image/png"),
                SimpleUploadedFile("invalid.png", b"<html>not a photo</html>", "image/png")]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PhotoEvidence.objects.count(), before)

    def test_failed_admin_invitation_keeps_administration_and_entered_values(self):
        # Real server validation after client-side validation is bypassed: no
        # invitation may be created and the user must be able to correct inputs.
        from .models import ProjectInvitation
        before = ProjectInvitation.objects.count()
        response = self.browser(self.admin).post(reverse("governance_invite"), {
            "email": "synthetic-invalid-email", "role": "ENGINEER",
            "project": self.project.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProjectInvitation.objects.count(), before)
        self.assertContains(response, 'name="email"', status_code=400,
            msg_prefix="The failing Admin invitation form must remain rendered")
        self.assertContains(response, 'value="synthetic-invalid-email"', status_code=400)
        self.assertContains(response, 'id="workspace-people-search"', status_code=400)


class AuditRepairImageParserTests(SimpleTestCase):
    def test_png_named_xbm_is_rejected_without_entering_disallowed_parser(self):
        from .photo_service import prepare_image
        # Benign 1px fixture, not a regex-exhaustion payload.
        raw = b"#define test_width 1\n#define test_height 1\nstatic char test_bits[] = {0x00};\n"
        with patch.object(XbmImagePlugin, "xbm_head", wraps=XbmImagePlugin.xbm_head) as expression:
            with self.assertRaises(ValidationError):
                prepare_image(SimpleUploadedFile("fake.png", raw, "image/png"))
        self.assertFalse(expression.match.called,
            "Disallowed plugins must not parse before the supported image-format boundary")


class AuditRepairGunicornParserTests(SimpleTestCase):
    """Exercise the real installed parser with bounded in-memory request bytes.

    Windows adapters cover only import-time POSIX identity/fd modules. Parser,
    framing validation, configuration defaults and body readers remain real.
    This does not replace the real Linux proxy acceptance check.
    """
    @contextmanager
    def parser_config(self):
        with ExitStack() as stack:
            if os.name == "nt":
                stack.enter_context(patch.dict(sys.modules,
                    {name: ModuleType(name) for name in ("grp", "pwd", "fcntl")}))
                stack.enter_context(patch.object(os, "geteuid", lambda: 0, create=True))
                stack.enter_context(patch.object(os, "getegid", lambda: 0, create=True))
            from gunicorn.config import Config
            yield Config()

    def test_actual_parser_keeps_valid_fixed_length_request_usable(self):
        with self.parser_config() as config:
            from gunicorn.http.parser import RequestParser
            raw = b"POST /synthetic-ok HTTP/1.1\r\nHost: synthetic.test\r\nContent-Length: 3\r\n\r\nabc"
            request = next(RequestParser(config, [raw], ("127.0.0.1", 1234)))
            self.assertEqual((request.method, request.path), ("POST", "/synthetic-ok"))
            self.assertEqual(request.body.read(), b"abc")

    def test_actual_parser_rejects_ambiguous_transfer_framing_and_header_names(self):
        with self.parser_config() as config:
            from gunicorn.http.parser import RequestParser
            from gunicorn.http.errors import InvalidHeader, InvalidHeaderName
            from gunicorn.http import errors
            rejections = (InvalidHeader, InvalidHeaderName)
            if hasattr(errors, "ObsoleteFolding"):
                rejections += (errors.ObsoleteFolding,)
            cases = (
                b"Transfer-Encoding: chunked\r\nContent-Length: 5",
                b"Transfer-Encoding: \x00chunked",
                b"Transfer-Encoding: chunked\r\nTransfer-Encoding: gzip",
                b"Transfer-Encoding : chunked",
                b"Content-Length: 3\r\nContent-Length: 4",
                b"Transfer-Encoding: chunked\r\n x",
            )
            for headers in cases:
                with self.subTest(headers=repr(headers)):
                    raw = b"POST /synthetic HTTP/1.1\r\nHost: synthetic.test\r\n" + headers + b"\r\n\r\n0\r\n\r\n"
                    with self.assertRaises(rejections):
                        next(RequestParser(config, [raw], ("127.0.0.1", 1234)))


@override_settings(SECRET_KEY="independent-history-repair-synthetic",
    ROOT_URLCONF="checklist.urls_local", ALLOWED_HOSTS=["testserver"],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditRepairHistoryBoundaryTests(TestCase):
    setUp = survey_fixture.SurveyProcessingTests.setUp
    person = survey_fixture.SurveyProcessingTests.person
    add_photo = survey_fixture.SurveyProcessingTests.add_photo

    def history_fixture(self):
        jobs = PhotoJob.objects.bulk_create([PhotoJob(checklist=self.checklist,
            requested_by=self.quality, model="synthetic-no-model-call",
            schema=self.checklist.schema_snapshot, status="running" if i == 0 else "queued")
            for i in range(110)])
        PhotoDraft.objects.bulk_create([PhotoDraft(job=jobs[-1], photo=self.photo,
            field_id="manufacturer", label="Synthetic historical proposal",
            value=None, reason="Synthetic isolated history only", uncertainty="high",
            status="pending" if i < 110 else "accepted") for i in range(115)])
        self.client.force_login(self.quality)
        return {job.pk for job in jobs}

    def test_history_is_bounded_but_every_retained_row_can_be_retrieved_once(self):
        expected_jobs = self.history_fixture()
        expected_drafts = set(PhotoDraft.objects.values_list("pk", flat=True))
        url = reverse("photo_state", args=[self.checklist.pk])
        initial = self.client.get(url)
        self.assertEqual(initial.status_code, 200)
        data = initial.json()
        self.assertLessEqual(len(data["jobs"]), 50)
        self.assertLessEqual(len(data["drafts"]), 50)
        self.assertEqual(data["analysis"]["active_job_count"], 110)
        self.assertEqual(data["analysis"]["workflow"]["stage"], "extracting_metadata",
            "A running job outside the visible history page must not become merely queued")
        for key, expected in (("jobs", expected_jobs), ("drafts", expected_drafts)):
            ids = [row["id"] for row in data[key]]
            meta = data["history"][key]
            self.assertEqual(meta["total"], len(expected))
            turns = 0
            while meta["has_more"]:
                turns += 1
                self.assertLess(turns, 10, "Pagination must terminate without cycling")
                response = self.client.get(url, {"history": key, "cursor": meta["next_cursor"]})
                self.assertEqual(response.status_code, 200, response.content)
                page = response.json()
                self.assertNotIn("photos", page, "History pagination must not serialize all evidence again")
                self.assertLessEqual(len(page[key]), 50)
                ids.extend(row["id"] for row in page[key])
                meta = page["history"][key]
            self.assertEqual(len(ids), len(set(ids)), "History pages must not duplicate entries")
            self.assertEqual(set(ids), expected)
        self.assertEqual(PhotoJob.objects.count(), 110)
        self.assertEqual(PhotoDraft.objects.count(), 115)

    def test_history_cursor_validation_and_foreign_access_do_not_expose_rows(self):
        self.history_fixture()
        url = reverse("photo_state", args=[self.checklist.pk])
        for query in ({"history": "anything"}, {"history": "jobs", "cursor": "-1:3"},
                      {"history": "drafts", "cursor": "2:3"},
                      {"history": "jobs", "cursor": "0:-4"},
                      {"history": "jobs", "cursor": "0:" + "9" * 100},
                      {"history": "jobs", "cursor": "0:1 OR 1=1"}):
            with self.subTest(query=query):
                response = self.client.get(url, query)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("jobs", response.json())
        company = Company.objects.create(name="History foreign company")
        project = Project.objects.create(name="History foreign project", company=company)
        actor = self.person("history_foreign", Profile.Roles.QUALITY_ENGINEER, project)
        self.client.force_login(actor)
        response = self.client.get(url, {"history": "jobs", "cursor": "0:100"})
        self.assertIn(response.status_code, (403, 404))
        self.assertNotContains(response, "Synthetic historical proposal", status_code=response.status_code)


@override_settings(ROOT_URLCONF="checklist.urls_local", ALLOWED_HOSTS=["testserver"],
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuditRepairDirectoryIsolationTests(TestCase):
    setUp = profile_fixture.WorkProfileTests.setUp
    person = profile_fixture.WorkProfileTests.person

    def test_directory_rechecks_effective_grants_after_successful_read(self):
        self.client.force_login(self.client_user)
        url = reverse("work_profile_directory")
        self.assertContains(self.client.get(url), self.record.display_name)
        grant = ProjectMembership.objects.get(user=self.engineer, project=self.project)
        grant.expires_at = timezone.now() - timedelta(seconds=1)
        grant.save(update_fields=["expires_at"])
        self.assertNotContains(self.client.get(url), self.record.display_name)
        grant.expires_at = None
        grant.is_active = False
        grant.save(update_fields=["expires_at", "is_active"])
        self.assertNotContains(self.client.get(url), self.record.display_name)
        grant.is_active = True
        grant.save(update_fields=["is_active"])
        self.assertContains(self.client.get(url), self.record.display_name)
        Profile.objects.filter(user=self.engineer).update(is_locked=True)
        self.assertNotContains(self.client.get(url), self.record.display_name)

