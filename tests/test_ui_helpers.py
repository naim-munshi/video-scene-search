"""UI helper coverage without Streamlit or local video model dependencies."""
import tempfile
import unittest
from pathlib import Path
from scene_search.ui_helpers import (discover_indexes, format_index,
                                     is_synthetic, readable_time, preview_frames)


class UIHelperTests(unittest.TestCase):
    def test_discover_preferred_and_completed_indexes(self):
        with tempfile.TemporaryDirectory() as temp:
            artifacts = Path(temp) / "artifacts"
            demo = artifacts / "demo-index-isolated"
            real = artifacts / "portfolio-real-v2"
            incomplete = artifacts / "building"
            for root in (demo, real, incomplete):
                root.mkdir(parents=True)
            for root in (demo, real):
                (root / "build.json").write_text("{}")
            rows = discover_indexes(artifacts, demo)
            self.assertEqual(rows, [demo, real])
            self.assertEqual(len(rows), len(set(rows)))
            self.assertNotIn(incomplete, rows)
            self.assertEqual(discover_indexes(artifacts)[0], real)

    def test_demo_detector_uses_metadata_not_count(self):
        self.assertTrue(is_synthetic([
            {"id": "demo_01", "title": "Synthetic demo 1"},
            {"id": "demo_02", "title": "Synthetic demo 2"}]))
        self.assertFalse(is_synthetic([
            {"id": "portfolio_nasa", "title": "NASA"},
            {"id": "portfolio_film", "title": "Tears of Steel"}]))
        self.assertFalse(is_synthetic([]))

    def test_readable_times(self):
        self.assertEqual(readable_time(0), "00:00")
        self.assertEqual(readable_time(887.6), "14:47")
        self.assertEqual(readable_time(3671), "1:01:11")

    def test_preview_frames_prefer_video_specific_safe_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "frames").mkdir()
            early = root / "frames" / "interview-begin.jpg"
            target = root / "frames" / "interview-best.jpg"
            other = root / "frames" / "nasa.jpg"
            for item in (early, target, other):
                item.write_bytes(b"thumbnail")
            videos = [
                {"id": "interview", "duration": 100},
                {"id": "nasa", "duration": 50},
                {"id": "missing", "duration": 20},
            ]
            frames = [
                {"video_id": "interview", "timestamp": 0,
                 "file": "frames/interview-begin.jpg"},
                {"video_id": "interview", "timestamp": 15,
                 "file": "frames/interview-best.jpg"},
                {"video_id": "nasa", "timestamp": 10, "file": "frames/nasa.jpg"},
            ]
            found = preview_frames(videos, frames, root)
            self.assertEqual(found["interview"], target)
            self.assertEqual(found["nasa"], other)
            self.assertIsNone(found["missing"])
            frames.append({"video_id": "missing", "timestamp": 3,
                           "file": "../../outside.jpg"})
            self.assertIsNone(preview_frames(videos, frames, root)["missing"])

    def test_index_labels(self):
        self.assertIn("DEMO", format_index("/tmp/demo-v1"))
        self.assertIn("LOCAL", format_index("/tmp/portfolio-real-v2"))


if __name__ == "__main__":
    unittest.main()
