"""Bounded regressions for the approved runtime/dependency audit findings."""
from importlib import metadata
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from packaging.requirements import Requirement
from packaging.version import Version
from PIL import Image

from core.photo_service import prepare_image


ROOT = Path(__file__).resolve().parents[2]


class DependencySecurityTests(SimpleTestCase):
    def test_apng_dimension_guard_precedes_background_canvas_allocation(self):
        # A normal, tiny APNG and a deliberately small test pixel limit. The
        # native allocation primitive is blocked, so no exhaustion payload runs.
        stream = BytesIO()
        Image.new('RGBA', (32, 32), 'red').save(
            stream, format='PNG', save_all=True,
            append_images=[Image.new('RGBA', (32, 32), 'blue')],
            disposal=1, duration=10, loop=0,
        )
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 16), patch.object(
            Image.core, 'fill', side_effect=AssertionError('Canvas allocated before dimension guard')
        ):
            with self.assertRaises(Image.DecompressionBombError):
                Image.open(BytesIO(stream.getvalue()), formats=['PNG'])

    def test_published_dependency_ranges_exclude_reviewed_vulnerable_versions(self):
        requirements = {}
        for line in (ROOT / 'backend/requirements.txt').read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                requirement = Requirement(line)
                requirements[requirement.name.lower()] = requirement.specifier
        self.assertNotIn(Version('10.4.0'), requirements['pillow'])
        self.assertNotIn(Version('12.3.0'), requirements['pillow'])
        self.assertIn(Version('13.0.0'), requirements['pillow'])
        self.assertNotIn(Version('21.2.0'), requirements['gunicorn'])
        self.assertIn(Version('26.2.2'), requirements['gunicorn'])

    def test_runtime_uses_reviewed_patched_image_decoder(self):
        self.assertGreaterEqual(Version(metadata.version('Pillow')), Version('13.0.0'))

    def test_bootstrap_installer_is_pinned_before_application_installation(self):
        bootstrap = ROOT / 'deploy/requirements.bootstrap.txt'
        self.assertTrue(bootstrap.is_file(), 'A reviewed bootstrap installer constraint is required')
        requirement = Requirement(bootstrap.read_text().strip())
        self.assertEqual(requirement.name.lower(), 'pip')
        self.assertNotIn(Version('25.0.1'), requirement.specifier)
        self.assertIn(Version('26.3'), requirement.specifier)
        dockerfile = (ROOT / 'deploy/Dockerfile').read_text()
        self.assertLess(
            dockerfile.index('-r /app/deploy/requirements.bootstrap.txt'),
            dockerfile.index('-r /app/backend/requirements.txt'),
        )

    def test_permitted_images_retain_original_bytes_and_capture_metadata(self):
        for image_format, extension in [('JPEG', 'jpg'), ('PNG', 'png'), ('WEBP', 'webp')]:
            with self.subTest(format=image_format):
                stream = BytesIO()
                exif = Image.Exif()
                exif[36867] = '2026:11:04 12:34:56'
                Image.new('RGB', (64, 48), 'green').save(stream, format=image_format, exif=exif)
                original = stream.getvalue()
                saved, preview, _, information, _ = prepare_image(
                    SimpleUploadedFile('site.' + extension, original)
                )
                self.assertEqual(saved, original)
                self.assertEqual(information['format'], image_format)
                self.assertEqual(information['captured_at'], '2026:11:04 12:34:56')
                self.assertEqual(information['width'], 64)
                self.assertEqual(information['height'], 48)
                with Image.open(BytesIO(preview)) as image:
                    self.assertEqual(image.format, 'JPEG')
                    self.assertEqual(image.size, (64, 48))
