"""Exact Git exports must be usable by the non-root image user under umask077."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class BuildContextPermissionTests(SimpleTestCase):
    def test_private_build_export_sets_image_readability_without_touching_source_or_private_data(self):
        spec = importlib.util.spec_from_file_location('shared_release_exporter', ROOT / 'deploy/staging.py')
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        with tempfile.TemporaryDirectory(dir=ROOT / '.local') as temporary:
            folder = Path(temporary)
            repository = folder / 'source'
            repository.mkdir()
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repository, text=True).strip()
            git('init', '-q')
            git('config', 'user.email', 'synthetic@example.invalid')
            git('config', 'user.name', 'Synthetic image permissions')
            git('config', 'core.autocrlf', 'false')
            (repository / 'backend').mkdir()
            (repository / 'backend/manage.py').write_bytes(b'print("SYNTHETIC ONLY")\n')
            (repository / 'start.sh').write_bytes(b'#!/bin/sh\nexit 0\n')
            (repository / '.gitignore').write_text('operator-private/\n')
            git('add', '.')
            git('update-index', '--chmod=+x', 'start.sh')
            git('commit', '-qm', 'Synthetic source for non-root image')
            release = git('rev-parse', 'HEAD')
            private = repository / 'operator-private'
            private.mkdir(mode=0o700)
            key = private / 'key'
            key.write_bytes(b'SYNTHETIC PRIVATE INPUT NEVER EXPORT')
            key.chmod(0o600)
            private_before = key.read_bytes(), key.stat().st_mode
            target = folder / 'export'
            chmod = Path.chmod
            applied = {}
            def record(path, mode, *args, **kwargs):
                applied[Path(path)] = mode
                return chmod(path, mode, *args, **kwargs)
            previous_mask = os.umask(0o077)
            try:
                with patch.object(Path, 'chmod', record):
                    exporter.prepare_release(repository, target, release)
            finally:
                os.umask(previous_mask)
            readable = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
            for path in (target / 'RELEASE', target / 'backend/manage.py'):
                self.assertIn(path, applied, 'Non-root image readability must not depend on the operator umask.')
                self.assertEqual(applied[path] & readable, readable)
            self.assertEqual(applied[target / 'backend'] & 0o555, 0o555)
            self.assertEqual(applied[target / 'start.sh'] & 0o111, 0o111)
            if os.name == 'posix':
                self.assertEqual((target / 'RELEASE').stat().st_mode & readable, readable)
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual((target / 'backend/manage.py').read_bytes(), (repository / 'backend/manage.py').read_bytes())
            self.assertEqual(hashlib.sha256(key.read_bytes()).digest(), hashlib.sha256(private_before[0]).digest())
            self.assertEqual(key.stat().st_mode, private_before[1])
            self.assertFalse((target / 'operator-private').exists())
