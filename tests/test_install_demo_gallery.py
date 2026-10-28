"""Contract tests: gallery images are verified before any local write."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from scripts import install_demo_gallery as gallery


class GalleryInstallerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / ".git").mkdir()
        self.zip_path = self.root / "demo.zip"
        self.file = "docs/assets/demo/01-overview.jpg"
        self.data = b"\xff\xd8\xff" + b"sample screenshot pixels"
        self.image_sha = hashlib.sha256(self.data).hexdigest()
        self.manifest = json.dumps(
            {"files": [{"file": self.file, "sha256": self.image_sha}]}).encode()
        self.gallery_md = b"# Demo gallery\n![UI](assets/demo/01-overview.jpg)\n"

    def create_zip(self, addition=None):
        files = {
            self.file: self.data,
            "docs/assets/demo/manifest.json": self.manifest,
            "docs/DEMO_GALLERY.md": self.gallery_md,
            "DEMO_ASSETS_README.txt": b"Owner-provided screenshots",
        }
        if addition:
            files.update(addition)
        with zipfile.ZipFile(self.zip_path, "w") as zf:
            for name, data in files.items():
                zf.writestr(name, data)
        return hashlib.sha256(self.zip_path.read_bytes()).hexdigest()

    def context(self, archive_sha):
        return patch.multiple(
            gallery, EXPECTED_ARCHIVE_SHA256=archive_sha,
            EXPECTED_IMAGES={self.file: self.image_sha})

    def test_verified_install_and_idempotency(self):
        sha = self.create_zip()
        with self.context(sha):
            installed = gallery.install(self.zip_path, self.root)
            self.assertIn(self.file, installed)
            self.assertEqual((self.root / self.file).read_bytes(), self.data)
            self.assertEqual(gallery.install(self.zip_path, self.root), installed)

    def test_rejects_changed_archive_before_writing(self):
        self.create_zip()
        with self.context("a" * 64):
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                gallery.install(self.zip_path, self.root)
        self.assertFalse((self.root / self.file).exists())

    def test_rejects_zip_extra_path(self):
        sha = self.create_zip({"../../outside.txt": b"attack"})
        with self.context(sha):
            with self.assertRaisesRegex(ValueError, "Unexpected"):
                gallery.install(self.zip_path, self.root)
        self.assertFalse((self.root / self.file).exists())

    def test_no_overwrite_existing_user_file(self):
        sha = self.create_zip()
        path = self.root / self.file
        path.parent.mkdir(parents=True)
        path.write_bytes(b"Edited image")
        with self.context(sha):
            with self.assertRaises(FileExistsError):
                gallery.install(self.zip_path, self.root)
        self.assertEqual(path.read_bytes(), b"Edited image")

    def test_missing_archive_has_helpful_error(self):
        with self.assertRaisesRegex(FileNotFoundError, "Download"):
            gallery.audit_bundle(self.root / "nonexistent.zip")


if __name__ == "__main__":
    unittest.main()
