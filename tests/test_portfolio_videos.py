"""No-network corpus manifest and rights metadata regression tests."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.prepare_portfolio_videos import VIDEOS, find_local_source, make_manifest, prepare


class PortfolioVideoTests(unittest.TestCase):
    def test_manifest_has_three_distinct_duration_checked_video_sources(self):
        result = make_manifest(["interview", "nasa", "film"])
        videos = result["videos"]
        self.assertEqual(len(videos), 3)
        self.assertEqual(len({v["id"] for v in videos}), 3)
        self.assertTrue(all(v["path"].startswith("videos/") for v in videos))
        self.assertTrue(all(v["rights_confirmed"] for v in videos))
        self.assertTrue(all(v["source"].startswith("https://") for v in videos))
        for spec in VIDEOS.values():
            self.assertTrue(600 <= spec["duration_seconds"] <= 1200)
            self.assertIn("license_url", spec)
            self.assertIn("attribution", spec)

    def test_partial_corpus_supported(self):
        self.assertEqual(len(make_manifest(["interview", "nasa"])["videos"]), 2)

    def test_existing_manual_webm_downloads_are_discovered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "interview.webm").write_bytes(b"x" * 100_001)
            (root / "tears_of_steel.webm").write_bytes(b"y" * 100_001)
            self.assertEqual(find_local_source("interview", root).name, "interview.webm")
            self.assertEqual(find_local_source("film", root).name, "tears_of_steel.webm")
            self.assertIsNone(find_local_source("nasa", root))

    def test_local_only_refuses_missing_source_without_network(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch("scripts.prepare_portfolio_videos.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("scripts.prepare_portfolio_videos.download") as fetch:
            with self.assertRaisesRegex(ValueError, "Local video source missing"):
                prepare(["film"], temp, local_only=True)
            fetch.assert_not_called()

    def test_local_conversion_keeps_original_and_prepares_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "videos" / "interview.webm"
            video.parent.mkdir()
            video.write_bytes(b"i" * 100_001)

            def simulate_conversion(args, **kwargs):
                Path(args[-1]).write_bytes(b"pretend encoded mp4")
                return SimpleNamespace(returncode=0)

            with patch("scripts.prepare_portfolio_videos.shutil.which", return_value="/usr/bin/ffmpeg"), \
                 patch("scripts.prepare_portfolio_videos.shutil.disk_usage",
                       return_value=SimpleNamespace(free=3_000_000_000)), \
                 patch("scripts.prepare_portfolio_videos.probe", return_value=888.0), \
                 patch("scripts.prepare_portfolio_videos.subprocess.run",
                       side_effect=simulate_conversion), \
                 patch("scripts.prepare_portfolio_videos.download") as fetch:
                output = prepare(["interview"], root, local_only=True)
            fetch.assert_not_called()
            self.assertTrue(video.exists())
            self.assertTrue((root / "videos" / "portfolio_interview.mp4").exists())
            self.assertEqual(Path(output["manifest"]).name, "portfolio-corpus.json")

    def test_invalid_selection_rejected(self):
        for videos in ([], ["film", "film"], ["not-real"]):
            with self.assertRaises(ValueError):
                make_manifest(videos)


if __name__ == "__main__":
    unittest.main()
