"""Synthetic demo fixtures: no ML models or downloaded media required."""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scene_search.core import make_windows, sha256, write_json

S = Path(__file__).resolve().parents[1] / "scripts" / "synthetic_demo.py"
spec = importlib.util.spec_from_file_location("synthetic_demo", S)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class SyntheticDemoTests(unittest.TestCase):
    def test_synthetic_ground_truth_is_24_queries_with_no_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index"
            index.mkdir()
            write_json(index / "build.json", {"fixture": True})
            windows = [w for i in range(1, 4) for w in make_windows(f"demo_{i:02d}", 30)]
            write_json(index / "windows.json", windows)
            out = root / "labels.json"
            demo.create_labels(index, out)
            labels = json.loads(out.read_text())
            self.assertEqual(labels["label_provenance"], "synthetic_deterministic_not_manual")
            self.assertEqual(labels["build_sha256"], sha256(index / "build.json"))
            self.assertEqual(len(labels["queries"]), 24)
            self.assertEqual([sum(q["split"] == split for q in labels["queries"])
                              for split in ("dev", "test")], [6, 18])
            self.assertEqual(len({q["text"] for q in labels["queries"]}), 24)
            self.assertTrue({q["relevant"][0] for q in labels["queries"]} <=
                            {w["id"] for w in windows})
            with self.assertRaisesRegex(ValueError, "already exist"):
                demo.create_labels(index, out)

    def test_metadata_preflight_checks_speech_and_duration(self):
        if not shutil.which("ffprobe"):
            self.skipTest("ffprobe missing")
        try:
            demo._require_ffmpeg()
        except RuntimeError as exc:
            self.skipTest(str(exc))
        import importlib.util
        spec = importlib.util.spec_from_file_location("real_video_preflight", S.parent / "real_video_preflight.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = demo.generate(Path(tmp))
            ok = module.preflight(manifest, min_seconds=29, max_seconds=31)
            self.assertTrue(ok["passed"], ok)
            self.assertEqual(len(ok["videos"]), 3)
            not_accepted = module.preflight(manifest)
            self.assertFalse(not_accepted["passed"])
            self.assertEqual(len(not_accepted["issues"]), 3)

    def test_wrong_corpus_cannot_receive_demo_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "windows.json", make_windows("other", 20))
            write_json(root / "build.json", {})
            with self.assertRaisesRegex(ValueError, "not the expected"):
                demo.create_labels(root, root / "out.json")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
    def test_generated_media_has_video_and_audio(self):
        try:
            demo._require_ffmpeg()
        except RuntimeError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = demo.generate(root)
            data = json.loads(manifest.read_text())
            self.assertEqual(len(data["videos"]), 3)
            self.assertTrue(all(v["rights_confirmed"] for v in data["videos"]))
            for v in data["videos"]:
                video = manifest.parent / v["path"]
                self.assertTrue(video.stat().st_size > 1000)
                probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                        "format=duration:stream=codec_type", "-of", "json", str(video)],
                                       check=True, text=True, capture_output=True)
                info = json.loads(probe.stdout)
                self.assertAlmostEqual(float(info["format"]["duration"]), 30.0, delta=0.3)
                self.assertTrue({"audio", "video"} <=
                                {stream["codec_type"] for stream in info["streams"]})
            with self.assertRaisesRegex(ValueError, "already exists"):
                demo.generate(root)


if __name__ == "__main__":
    unittest.main()
