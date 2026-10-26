"""No-network corpus manifest and rights metadata regression tests."""
import unittest

from scripts.prepare_portfolio_videos import VIDEOS, make_manifest


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

    def test_invalid_selection_rejected(self):
        for videos in ([], ["film", "film"], ["not-real"]):
            with self.assertRaises(ValueError):
                make_manifest(videos)


if __name__ == "__main__":
    unittest.main()
