"""Real filesystem redirect fixtures without suppressing permission failures.

The original security boundary is directory redirection. Native symlinks remain
the first choice; the approved Windows privilege fallback is tested separately.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase


@contextmanager
def directory_redirect(link, target):
    """Create a real native link, or a Windows junction only for WinError1314.

    The fallback does not simulate a link and does not claim native Windows
    symlink coverage. Every other OS/permission/creation failure still fails.
    """
    link, target = Path(link), Path(target)
    if link.exists() or link.is_symlink() or link.is_junction():
        raise FileExistsError('A redirect fixture cannot replace an existing destination')
    if not target.is_dir():
        raise NotADirectoryError('A redirect fixture requires an existing directory target')
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name != 'nt' or getattr(exc, 'winerror', None) != 1314:
            raise
        powershell = shutil.which('powershell.exe') or shutil.which('pwsh')
        if not powershell:
            raise RuntimeError('The genuine Windows junction fixture requires PowerShell') from exc
        environment = {**os.environ, 'ISURVIX_TEST_REDIRECT_LINK': str(link.absolute()),
            'ISURVIX_TEST_REDIRECT_TARGET': str(target.resolve(strict=True))}
        subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-Command',
            "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction "
            '-Path $env:ISURVIX_TEST_REDIRECT_LINK '
            '-Target $env:ISURVIX_TEST_REDIRECT_TARGET | Out-Null'],
            env=environment, check=True, capture_output=True, timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        if not (link.is_symlink() or link.is_junction()) or not link.samefile(target):
            raise AssertionError('The fixture must be a physical redirect to its exact target')
        yield link
    finally:
        # Remove this fixture node only; never recursively follow/delete target.
        if link.is_junction():
            os.rmdir(link)
        elif link.is_symlink():
            link.unlink()
        elif link.exists():
            raise AssertionError('The redirect fixture was unexpectedly replaced')


class DirectoryRedirectFixtureTests(SimpleTestCase):
    def setUp(self):
        location = Path(__file__).resolve().parents[2] / '.local/redirect-fixture-tests'
        location.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='redirect-', dir=location)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.target = self.base / 'separate-target'
        self.target.mkdir()
        self.marker = self.target / 'retained.txt'
        self.marker.write_bytes(b'Synthetic retained target bytes')
        self.link = self.base / 'redirect'

    def assert_real_redirect(self, redirect):
        self.assertTrue(redirect.is_symlink() or redirect.is_junction())
        self.assertTrue(redirect.samefile(self.target))
        self.assertEqual((redirect / 'retained.txt').read_bytes(), self.marker.read_bytes())

    def test_default_fixture_is_a_real_redirect_and_cleanup_preserves_target(self):
        with directory_redirect(self.link, self.target) as redirect:
            self.assert_real_redirect(redirect)
        self.assertFalse(self.link.exists())
        self.assertFalse(self.link.is_symlink())
        self.assertFalse(self.link.is_junction())
        self.assertEqual(self.marker.read_bytes(), b'Synthetic retained target bytes')

    def test_windows_privilege_only_fallback_creates_a_genuine_junction(self):
        error = OSError('Synthetic missing symbolic-link privilege')
        error.winerror = 1314
        with patch.object(Path, 'symlink_to', side_effect=error):
            if os.name == 'nt':
                with directory_redirect(self.link, self.target) as redirect:
                    self.assertTrue(redirect.is_junction())
                    self.assertFalse(redirect.is_symlink())
                    self.assert_real_redirect(redirect)
            else:
                with self.assertRaises(OSError) as raised:
                    with directory_redirect(self.link, self.target):
                        self.fail('Windows junction fallback must never run on another platform')
                self.assertIs(raised.exception, error)
        self.assertEqual(self.marker.read_bytes(), b'Synthetic retained target bytes')

    def test_an_unrelated_permission_failure_is_not_suppressed(self):
        error = PermissionError('Synthetic access denied')
        error.winerror = 5
        with patch.object(Path, 'symlink_to', side_effect=error):
            with self.assertRaises(PermissionError) as raised:
                with directory_redirect(self.link, self.target):
                    self.fail('Unrelated permission failures must not be hidden')
        self.assertIs(raised.exception, error)
        self.assertFalse(self.link.exists())
        self.assertEqual(self.marker.read_bytes(), b'Synthetic retained target bytes')

    def test_existing_destination_is_never_replaced(self):
        self.link.mkdir()
        retained = self.link / 'existing.txt'
        retained.write_bytes(b'Existing fixture destination')
        with self.assertRaises(FileExistsError):
            with directory_redirect(self.link, self.target):
                self.fail('Existing destinations must not be overwritten')
        self.assertEqual(retained.read_bytes(), b'Existing fixture destination')
        self.assertEqual(self.marker.read_bytes(), b'Synthetic retained target bytes')
