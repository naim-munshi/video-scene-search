"""Pure metadata index acceptance tests (no ML dependency or native FAISS load)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.acceptance_check import audit_index
from scene_search.pipeline import VISUAL_MODEL, TEXT_MODEL
from scene_search.core import write_json, sha256


class AcceptanceTests(unittest.TestCase):
    def make_index(self, base):
        root = Path(base)
        (root / "frames").mkdir()
        (root / "frames/f.jpg").write_bytes(b"synthetic frame")
        (root / "visual.faiss").write_bytes(b"test-only index placeholder")
        write_json(root / "corpus.json", {"videos": [{
            "id": "clip", "duration": 10, "path": str(root / "video.mp4"),
            "title": "Local self-recording"
        }]})
        (root / "video.mp4").write_bytes(b"test only")
        write_json(root / "windows.json", [{
            "id": "clip:00000", "video_id": "clip", "start": 0, "end": 10
        }])
        write_json(root / "frames.json", [{
            "file": "frames/f.jpg", "video_id": "clip", "timestamp": 0,
            "window_ids": ["clip:00000"]
        }])
        write_json(root / "segments.json", [])
        names = ("corpus.json", "windows.json", "frames.json", "segments.json",
                 "frames/f.jpg", "visual.faiss")
        write_json(root / "build.json", {
            "schema_version": 1, "visual_model": VISUAL_MODEL,
            "text_model": TEXT_MODEL,
            "files": {p: sha256(root / p) for p in names}
        })
        return root

    def test_complete_local_metadata_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_index(td)
            report = audit_index(root)
            self.assertEqual(report["status"], "metadata_integrity_passed")
            self.assertEqual(report["video_count"], 1)
            self.assertEqual(report["sampled_frames"], 1)
            self.assertEqual(report["warnings"], [])

    def test_modified_frame_fails_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_index(td)
            (root / "frames/f.jpg").write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "integrity"):
                audit_index(root)

    def test_invalid_cross_video_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = self.make_index(td)
            write_json(root / "frames.json", [{
                "file": "frames/f.jpg", "video_id": "clip", "timestamp": 0,
                "window_ids": ["clip:99999"]
            }])
            build = json.loads((root / "build.json").read_text())
            build["files"]["frames.json"] = sha256(root / "frames.json")
            write_json(root / "build.json", build)
            with self.assertRaisesRegex(ValueError, "window reference"):
                audit_index(root)

    def test_missing_build_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "build.json"):
                audit_index(td)


if __name__ == "__main__":
    unittest.main()
