"""Tests for truthful local v0.1 closeout without touching original media."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.final_acceptance import evaluate_acceptance, review_browser


BUILD = "a" * 64
VIDS = ["portfolio_interview", "portfolio_film", "portfolio_nasa"]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class FinalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.release = root / "release"
        self.release.mkdir()
        self.media = root / "media.json"
        self.browser = root / "browser.json"
        write(self.release / "RELEASE_STATUS.json", {
            "status": "LOCAL_ENGINEERING_CHECKS_PASS",
            "development_queries": 6, "provisional_test_queries": 18,
            "accuracy_provenance": "AI_ASSISTED_WEAK_LABELS_ONLY"})
        write(self.release / "input-manifest.json", {
            "index_build_sha256": BUILD, "independently_verified": False,
            "query_counts": {"dev": 6, "test": 18},
            "index_metadata_audit": {
                "status": "metadata_integrity_passed",
                "video_count": 3, "window_count": 252,
                "warnings": [], "build_sha256": BUILD}})
        for folder in ("dev", "test"):
            for name in ("report.md", "metrics.csv", "per_query.json"):
                p = self.release / folder / name
                p.parent.mkdir(exist_ok=True)
                p.write_text("evidence", encoding="utf-8")
        (self.release / "RELEASE_SUMMARY.md").write_text(
            "AI-ASSISTED WEAK LABELS not independently verified", encoding="utf-8")
        write(self.media, {
            "status": "LOCAL_MEDIA_DECODE_PASS",
            "browser_playback_status": "NOT_VERIFIED",
            "source_count": 3,
            "sources": [
                {"video_id": vid, "status": "LOCAL_MEDIA_DECODE_PASS",
                 "video_codec": "h264", "audio_codec": "aac",
                 "decoded_frame_checkpoints_seconds": [5, 300, 585],
                 "audio_decoded_seconds": 2}
                for vid in VIDS]})
        write(self.browser, {
            "status": "USER_SELF_ATTESTED",
            "source": "manual_Streamlit_checkbox_self_attestation",
            "not_automated_safari_test": True,
            "independent_ground_truth_verified": False,
            "build_sha256": BUILD,
            "expected_sources": VIDS,
            "checkpoints_per_video": ["Beginning", "Middle", "Near end"],
            "confirmed_checkpoints": 9, "required_checkpoints": 9,
            "recorded_at_utc": "2026-10-27T05:50:00+00:00"})

    def test_engineering_and_media_pass_without_human_browser_claim(self):
        x = evaluate_acceptance(self.release, self.media)
        self.assertEqual(x["engineering"]["status"], "PASS")
        self.assertEqual(x["native_media_decoding"]["status"], "PASS")
        self.assertEqual(x["browser_picture_sound"]["status"], "NOT_VERIFIED")
        self.assertEqual(x["overall"], "LOCAL_ENGINEERING_PASS_BROWSER_PENDING")
        self.assertEqual(x["independent_ground_truth"], "NOT_VERIFIED")
        self.assertEqual(x["production_hosting_security"], "OUT_OF_SCOPE")

    def test_nine_human_checks_only_self_attest_not_browser_certification(self):
        x = evaluate_acceptance(self.release, self.media, self.browser)
        self.assertEqual(x["overall"], "LOCAL_PORTFOLIO_OPERATOR_SELF_ATTESTED")
        self.assertEqual(x["browser_picture_sound"]["status"], "USER_SELF_ATTESTED")
        self.assertFalse(x["browser_picture_sound"]["independent_browser_certification"])

    def test_wrong_build_rejected(self):
        payload = json.loads(self.browser.read_text())
        payload["build_sha256"] = "b" * 64
        write(self.browser, payload)
        with self.assertRaisesRegex(ValueError, "incomplete or inconsistent"):
            review_browser(self.browser, BUILD)

    def test_incomplete_eight_of_nine_does_not_claim_acceptance(self):
        payload = json.loads(self.browser.read_text())
        payload["confirmed_checkpoints"] = 8
        write(self.browser, payload)
        with self.assertRaises(ValueError):
            evaluate_acceptance(self.release, self.media, self.browser)

    def test_corrupted_media_evidence_blocks(self):
        payload = json.loads(self.media.read_text())
        payload["sources"][0]["audio_codec"] = "invalid"
        write(self.media, payload)
        with self.assertRaisesRegex(ValueError, "audio/video"):
            evaluate_acceptance(self.release, self.media)

    def test_release_needs_correct_provenance(self):
        payload = json.loads((self.release / "input-manifest.json").read_text())
        payload["independently_verified"] = True
        write(self.release / "input-manifest.json", payload)
        with self.assertRaisesRegex(ValueError, "provenance"):
            evaluate_acceptance(self.release, self.media)

    def test_release_does_not_write_or_overwrite_evidence(self):
        before = {p: p.read_bytes() for p in self.release.rglob("*") if p.is_file()}
        _ = evaluate_acceptance(self.release, self.media)
        after = {p: p.read_bytes() for p in self.release.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
