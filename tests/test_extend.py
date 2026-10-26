"""Check incremental extension eligibility without loading native FAISS or ML."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scene_search.core import read_json, sha256, write_json
from scene_search.extend import extension_plan
from scene_search.pipeline import TEXT_MODEL, VISUAL_MODEL
from scripts.add_nasa_video import create_three_video_manifest, find_nasa_source
from scripts.prepare_portfolio_videos import VIDEOS


def video_entry(vid, path):
    return {"id": vid, "path": str(path), "title": vid,
            "source": "self-created", "license": "test-licensed",
            "attribution": "test", "rights_confirmed": True}


class ExtensionPlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = self.root / "index-v1"
        self.base.mkdir()
        self.first = self.root / "first.mp4"
        self.second = self.root / "second.mp4"
        self.first.write_bytes(b"owned first movie")
        self.second.write_bytes(b"owned second movie")
        video = video_entry("first", self.first)
        video["sha256"] = sha256(self.first)
        video["duration"] = 600
        self.video = video
        write_json(self.base / "corpus.json", {"videos": [video]})
        build = {
            "schema_version": 1, "visual_model": VISUAL_MODEL,
            "text_model": TEXT_MODEL,
            "whisper_model": "base", "language": "en",
            "embedding_device": "mps", "frame_seconds": 2,
            "window_seconds": 10, "visual_batch_size": 2,
            "files": {"corpus.json": sha256(self.base / "corpus.json")},
        }
        write_json(self.base / "build.json", build)
        self.manifest = self.root / "three.json"
        self.new = video_entry("second", self.second)
        write_json(self.manifest, {"videos": [video_entry("first", self.first), self.new]})

    def test_valid_one_video_append_plan(self):
        plan = extension_plan(self.base, self.manifest, self.root / "index-v2")
        self.assertEqual(plan["added"]["id"], "second")
        self.assertEqual(len(plan["original"]), 1)

    def test_changed_old_source_rejected(self):
        self.first.write_bytes(b"altered original")
        with self.assertRaisesRegex(ValueError, "Source video changed"):
            extension_plan(self.base, self.manifest, self.root / "index-v2")

    def test_missing_or_duplicate_increment_rejected(self):
        write_json(self.manifest, {"videos": [video_entry("first", self.first)]})
        with self.assertRaisesRegex(ValueError, "one additional"):
            extension_plan(self.base, self.manifest, self.root / "index-v2")
        write_json(self.manifest, {"videos": [video_entry("first", self.first), self.new]})
        with self.assertRaisesRegex(ValueError, "overwrite"):
            extension_plan(self.base, self.manifest, self.base)

    def test_corrupt_prior_index_rejected(self):
        (self.base / "corpus.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "integrity"):
            extension_plan(self.base, self.manifest, self.root / "index-v2")


class NasaManifestTests(unittest.TestCase):
    def test_autodiscovery_without_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "videos").mkdir()
            local = root / "videos" / "nasa_apollo15.mp4"
            local.write_bytes(b"nasa file")
            self.assertEqual(find_nasa_source(root), local)
            with self.assertRaisesRegex(ValueError, "NASA source not found"):
                find_nasa_source(root, explicit=str(root / "missing.mp4"))

    def test_three_video_manifest_reuses_existing_two(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            videos = root / "videos"
            videos.mkdir(parents=True)
            first = videos / "portfolio_interview.mp4"
            film = videos / "portfolio_film.mp4"
            nasa = videos / "nasa_apollo15.mp4"
            for path in (first, film, nasa):
                path.write_bytes(b"video file")
            prior = {
                "videos": [
                    {**video_entry("portfolio_interview", first), "path": "videos/portfolio_interview.mp4"},
                    {**video_entry("portfolio_film", film), "path": "videos/portfolio_film.mp4"},
                ]
            }
            write_json(root / "portfolio-corpus.json", prior)
            with patch("scripts.add_nasa_video.probe", return_value=887.0):
                result = create_three_video_manifest(root)
                again = create_three_video_manifest(root)
            self.assertEqual(result["manifest"], again["manifest"])
            created = read_json(root / "portfolio-corpus-3.json")
            self.assertEqual(len(created["videos"]), 3)
            self.assertEqual(created["videos"][:2], prior["videos"])
            self.assertEqual(created["videos"][2]["id"], "portfolio_nasa")
            self.assertTrue(nasa.exists())

    def test_missing_nasa_file_fails_clear(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            (root / "videos").mkdir(parents=True)
            one = root / "videos" / "portfolio_interview.mp4"
            two = root / "videos" / "portfolio_film.mp4"
            for path in (one, two):
                path.write_bytes(b"local source")
            write_json(root / "portfolio-corpus.json", {
                "videos": [{**video_entry("portfolio_interview", one),
                            "path": "videos/portfolio_interview.mp4"},
                           {**video_entry("portfolio_film", two),
                            "path": "videos/portfolio_film.mp4"}]})
            with patch("scripts.add_nasa_video.find_nasa_source", return_value=None):
                with self.assertRaisesRegex(ValueError, "NASA MP4 not found"):
                    create_three_video_manifest(root)


if __name__ == "__main__":
    unittest.main()
