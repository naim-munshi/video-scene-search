"""UI helper coverage without Streamlit or local video model dependencies."""
import tempfile
import unittest
from pathlib import Path
from scene_search.ui_helpers import (discover_indexes, format_index,
                                     is_synthetic, readable_time, preview_frames,
                                     playback_checkpoints, browser_checklist_status,
                                     playback_confirmation_key,
                                     collect_playback_confirmations)


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

    def test_playback_checkpoints_and_manual_browser_attestation(self):
        self.assertEqual(playback_checkpoints(900),
                         [("Beginning", 5), ("Middle", 450), ("Near end", 885)])
        with self.assertRaises(ValueError):
            playback_checkpoints(0)
        ids = ["portfolio_nasa", "portfolio_interview", "portfolio_film"]
        checks = {v: {name: True for name in
                  ("Beginning", "Middle", "Near end")} for v in ids}
        status = browser_checklist_status("validhash", checks, ids)
        self.assertEqual(status["status"], "USER_SELF_ATTESTED")
        self.assertTrue(status["not_automated_safari_test"])
        self.assertFalse(status["independent_ground_truth_verified"])
        checks["portfolio_film"]["Near end"] = False
        status = browser_checklist_status("validhash", checks, ids)
        self.assertEqual(status["status"], "NOT_VERIFIED")
        self.assertEqual(status["confirmed_checkpoints"], 8)
        self.assertEqual(browser_checklist_status("digest", {}, ids)["status"],
                         "NOT_VERIFIED")

    def test_playback_confirmations_survive_hidden_widget_state(self):
        from hashlib import sha256
        digest = sha256(b"first index").hexdigest()
        other = sha256(b"second index").hexdigest()
        ids = ["portfolio_nasa", "portfolio_interview", "portfolio_film"]
        persistent = {}
        # Only the current widget is rendered at any given time in Streamlit.
        # Prior checkpoint widgets disappear, but this backing store persists.
        for vid in ids:
            for step in ("Beginning", "Middle", "Near end"):
                key = playback_confirmation_key(digest, vid, step)
                persistent[key] = True
        observed = collect_playback_confirmations(persistent, digest, ids)
        self.assertEqual(browser_checklist_status(digest, observed, ids)["status"],
                         "USER_SELF_ATTESTED")
        self.assertEqual(browser_checklist_status(other,
            collect_playback_confirmations(persistent, other, ids), ids)["status"],
            "NOT_VERIFIED")
        persistent.pop(playback_confirmation_key(digest, ids[1], "Middle"))
        after_revocation = collect_playback_confirmations(persistent, digest, ids)
        self.assertEqual(browser_checklist_status(digest,
            after_revocation, ids)["confirmed_checkpoints"], 8)
        self.assertFalse(after_revocation[ids[1]]["Middle"])

    def test_playback_confirmation_keys_are_full_build_scoped(self):
        from hashlib import sha256
        digest = sha256(b"some index").hexdigest()
        value = playback_confirmation_key(digest, "portfolio_nasa", "Beginning")
        self.assertIn(digest, value)
        for bad in ("digest", "", None):
            with self.assertRaises(ValueError):
                playback_confirmation_key(bad, "portfolio_nasa", "Beginning")
        with self.assertRaises(ValueError):
            playback_confirmation_key(digest, "portfolio_nasa", "Not a checkpoint")

    def test_index_labels(self):
        self.assertIn("DEMO", format_index("/tmp/demo-v1"))
        self.assertIn("LOCAL", format_index("/tmp/portfolio-real-v2"))


if __name__ == "__main__":
    unittest.main()
