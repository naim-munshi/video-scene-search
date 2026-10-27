"""Evidence-export tests: no search ranking or ML inference is involved."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scene_search.core import sha256, write_json
from scripts.export_annotation_evidence import (
    build_evidence, choose_two_images, export_evidence, make_queries,
    token_overlap,
)


class EvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "index"
        self.root.mkdir()
        self.videos = ("portfolio_interview", "portfolio_film", "portfolio_nasa")
        frames, windows, corpus, segments = [], [], [], []
        (self.root / "frames").mkdir()
        for video in self.videos:
            corpus.append({"id": video, "title": video,
                           "duration": 10, "path": "/private/original.mp4"})
            wid = video + ":00000"
            windows.append({"id": wid, "video_id": video,
                            "start": 0, "end": 10})
            path = f"frames/{video}.jpg"
            frames.append({"video_id": video, "timestamp": 2,
                           "file": path, "window_ids": [wid]})
            (self.root / path).write_bytes(b"fixture thumbnail")
            segments.append({
                "video_id": video, "start": 0, "end": 5,
                "text": ("Talking about space mission" if video.endswith("nasa")
                         else "Someone talking about technology"),
                "window_ids": [wid],
            })
        for name, content in (("corpus.json", {"videos": corpus}),
                              ("windows.json", windows),
                              ("frames.json", frames),
                              ("segments.json", segments)):
            write_json(self.root / name, content)
        write_json(self.root / "build.json", {
            "schema_version": 1,
            "files": {name: sha256(self.root / name) for name in
                      ("corpus.json", "windows.json",
                       "frames.json", "segments.json")},
        })

    def test_query_texts_are_candidates_not_ground_truth(self):
        queries = make_queries(self.root)
        self.assertEqual(queries["status"], "unverified_model_assisted")
        self.assertEqual(len(queries["queries"]), 24)
        self.assertTrue(all(not q["relevant"] for q in queries["queries"]))
        self.assertEqual(
            sum(q["split"] == "test" for q in queries["queries"]), 18)

    def test_evidence_per_window_with_transcripts(self):
        r = build_evidence(self.root)
        self.assertEqual(len(r["records"]), 3)
        self.assertEqual(len(r["frame_map"]), 3)
        self.assertTrue(all(x["frames_available"] == 1 for x in r["records"]))
        speech_hints = next(h for h in r["keyword_hints"]
                            if h["query_id"] == "q01")
        self.assertTrue(speech_hints["weak_transcript_keyword_hints"])
        self.assertEqual(
            speech_hints["weak_transcript_keyword_hints"][0]["window_id"],
            "portfolio_nasa:00000")

    def test_keyword_hints_are_lexical_and_allow_no_match(self):
        self.assertEqual(token_overlap("space mission narration",
                                       "The SPACE mission launched"), ["mission", "space"])
        self.assertEqual(token_overlap("yellow car", "a person runs"), [])

    def test_choose_two_images(self):
        self.assertEqual(choose_two_images([]), [])
        one = [{"timestamp": 5}]
        self.assertEqual(choose_two_images(one), one)
        many = [{"timestamp": i} for i in range(6)]
        self.assertEqual([x["timestamp"] for x in choose_two_images(many)],
                         [1, 4])

    def test_invalid_metadata_sha_is_rejected(self):
        (self.root / "segments.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "integrity"):
            build_evidence(self.root)

    def test_uploaded_query_draft_must_match_index(self):
        draft = self.root.parent / "queries.json"
        obj = make_queries(self.root)
        write_json(draft, obj)
        actual = make_queries(self.root, draft)
        self.assertEqual(actual["queries"][0]["id"], "q01")
        obj["build_sha256"] = "invalid"
        write_json(draft, obj)
        with self.assertRaisesRegex(ValueError, "different"):
            make_queries(self.root, draft)

    def test_generate_contact_sheets_when_pillow_present(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed in lightweight CI")
        for video in self.videos:
            Image.new("RGB", (64, 48), "navy").save(
                self.root / "frames" / f"{video}.jpg")
        output = self.root.parent / "evidence.zip"
        result = export_evidence(self.root, output)
        self.assertEqual(result["window_count"], 3)
        self.assertEqual(result["candidate_queries"], 24)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            sheets = [name for name in names
                      if name.startswith("contact_sheets/")]
            self.assertEqual(len(sheets), 3)
            self.assertIn("windows_and_transcripts.json", names)
            self.assertIn("queries.json", names)
            queries = json.loads(archive.read("queries.json"))
            self.assertEqual(queries["status"], "unverified_model_assisted")
            self.assertTrue(all(not q["relevant"] for q in queries["queries"]))
        with self.assertRaisesRegex(ValueError, "exists"):
            export_evidence(self.root, output)


if __name__ == "__main__":
    unittest.main()
