"""No network, no media upload model: validate staged corpus safety."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from scene_search.uploads import (MAX_UPLOAD_BYTES, stage_upload,
                                  validate_import_fields)


class FakeUpload(io.BytesIO):
    def __init__(self, data, name="camera.mp4"):
        super().__init__(data)
        self.name = name
        self.size = len(data)


class UploadTests(unittest.TestCase):
    def test_validation_guards(self):
        args = ("clip.mp4", 100, "Clip", "Self-recorded", "Own work", "Creator", True)
        validate_import_fields(*args)
        with self.assertRaisesRegex(ValueError, "permission"):
            validate_import_fields(*args[:-1], False)
        with self.assertRaisesRegex(ValueError, "MP4"):
            validate_import_fields("x.exe", *args[1:])
        with self.assertRaisesRegex(ValueError, "250 MiB"):
            validate_import_fields(args[0], MAX_UPLOAD_BYTES + 1, *args[2:])

    def test_stage_creates_isolated_new_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            source = FakeUpload(b"video-file-placeholder")
            with patch("scene_search.uploads.verify_video", return_value=37.6), \
                 patch("scene_search.uploads.shutil.disk_usage",
                       return_value=SimpleNamespace(free=5_000_000_000)):
                info = stage_upload(source, "A clip", "My camera",
                                    "Self-recorded", "Me", True, Path(td))
            manifest = Path(info["manifest"])
            self.assertTrue(manifest.is_file())
            self.assertTrue((manifest.parent / "clip.mp4").is_file())
            self.assertEqual(manifest.parent.parent, Path(td))
            self.assertEqual(info["duration_seconds"], 37.6)

    def test_failed_probe_cleans_all_staging(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("scene_search.uploads.verify_video",
                       side_effect=ValueError("Bad media")), \
                 patch("scene_search.uploads.shutil.disk_usage",
                       return_value=SimpleNamespace(free=5_000_000_000)):
                with self.assertRaisesRegex(ValueError, "Bad media"):
                    stage_upload(FakeUpload(b"bad"), "Clip",
                                 "Self", "Own", "Creator", True, Path(td))
            self.assertEqual(list(Path(td).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
