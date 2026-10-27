"""Dependency-free tests for read-only FFmpeg media acceptance gating."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.media_playback_preflight import (
    check_media, check_source, sample_seconds,
)


class MediaPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "clip.mp4"
        self.file.write_bytes(b"placeholder media; mocked probe")
        self.calls = []

    def fake_runner(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == "ffprobe":
            return SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({
                    "format": {"duration": "600.0"},
                    "streams": [
                        {"codec_type": "video", "codec_name": "h264"},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                }))
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    def video(self, vid="film"):
        return {"id": vid, "path": str(self.file), "duration": 600}

    def test_sample_points_stay_inside_original(self):
        self.assertEqual(sample_seconds(600), [5.0, 300.0, 585.0])
        with self.assertRaisesRegex(ValueError, "15 seconds"):
            sample_seconds(10)

    def test_checks_probe_and_three_video_plus_audio_decodes(self):
        r = check_source(self.video(), runner=self.fake_runner)
        self.assertEqual(r["status"], "LOCAL_MEDIA_DECODE_PASS")
        self.assertEqual(r["decoded_frame_checkpoints_seconds"], [5, 300, 585])
        self.assertEqual(len(self.calls), 5)
        self.assertEqual([x[0] for x in self.calls], ["ffprobe"] + ["ffmpeg"] * 4)
        self.assertEqual(sum("-frames:v" in x for x in self.calls), 3)
        self.assertEqual(sum("-vn" in x for x in self.calls), 1)
        self.assertTrue(all("-nostdin" in x for x in self.calls[1:]))
        self.assertEqual(self.file.read_bytes(), b"placeholder media; mocked probe")

    def test_rejects_missing_source(self):
        self.file.unlink()
        with self.assertRaises(FileNotFoundError):
            check_source(self.video(), runner=self.fake_runner)

    def test_rejects_nonbrowser_codec(self):
        def bad(command, **kwargs):
            result = self.fake_runner(command, **kwargs)
            if command[0] == "ffprobe":
                meta = json.loads(result.stdout)
                meta["streams"][0]["codec_name"] = "vp9"
                result.stdout = json.dumps(meta)
            return result
        with self.assertRaisesRegex(ValueError, "H.264/AAC"):
            check_source(self.video(), runner=bad)
        self.assertEqual(len(self.calls), 1)

    def test_failing_decoder_blocks_pass(self):
        def fail(command, **kwargs):
            result = self.fake_runner(command, **kwargs)
            if command[0] == "ffmpeg":
                result.returncode = 1
                result.stderr = "decode failure"
            return result
        with self.assertRaisesRegex(RuntimeError, "decode failure"):
            check_source(self.video(), runner=fail)

    def test_three_source_check_never_claims_browser_acceptance(self):
        videos = [self.video(vid) for vid in (
            "portfolio_nasa", "portfolio_interview", "portfolio_film")]
        with patch("scripts.media_playback_preflight.audit_index", return_value={
            "status": "metadata_integrity_passed", "warnings": []
        }), patch("scripts.media_playback_preflight.read_json",
                 return_value={"videos": videos}):
            r = check_media(self.root, runner=self.fake_runner)
        self.assertEqual(r["source_count"], 3)
        self.assertEqual(r["browser_playback_status"], "NOT_VERIFIED")
        self.assertEqual(r["human_audio_visual_review"], "NOT_VERIFIED")
        self.assertEqual(len(self.calls), 15)


if __name__ == "__main__":
    unittest.main()
