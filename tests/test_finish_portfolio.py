"""Tests for the local, non-destructive 3-video portfolio release gate."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scene_search.core import read_json, sha256, write_json
from scripts.finish_portfolio import (
    finish, inspect_release_inputs, make_summary, summary_table,
)


def totals():
    return [
        {"mode": mode, "kind": "all",
         "recall@5": .4, "hit@5": .6, "mrr@5": .5}
        for mode in ("visual", "transcript", "hybrid")
    ]


class PortfolioFinishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.index = base / "index"
        self.index.mkdir()
        self.labels = base / "labels.json"
        self.output = base / "release"
        videos = ("portfolio_nasa", "portfolio_interview", "portfolio_film")
        write_json(self.index / "build.json", {"fixture": True})
        write_json(self.index / "corpus.json", {
            "videos": [{"id": x, "path": "/not/existing"} for x in videos]})
        write_json(self.index / "windows.json", [
            {"id": x + ":00000", "video_id": x, "start": 0, "end": 10}
            for x in videos])
        self.data = {
            "status": "annotated",
            "build_sha256": sha256(self.index / "build.json"),
            "annotation_method": "assistant_assisted_contact_sheets_and_asr",
            "human_verified": False,
            "independent_ground_truth": False,
            "queries": [
                {"id": f"q{i+1:02d}", "text": f"Unique example {i}",
                 "kind": ("speech", "visual", "mixed")[i % 3],
                 "split": "dev" if i < 6 else "test",
                 "relevant": [videos[i % 3] + ":00000"]}
                for i in range(24)],
        }
        write_json(self.labels, self.data)
        self.audit = patch("scripts.acceptance_check.audit_index",
                           return_value={"status": "PASS"})
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def test_24_query_preflight_and_no_media_modification(self):
        manifest = inspect_release_inputs(self.index, self.labels)
        self.assertEqual(manifest["query_counts"], {"dev": 6, "test": 18})
        self.assertFalse(manifest["independently_verified"])
        self.assertTrue(manifest["assistant_assisted_weak_labels"])
        self.assertEqual(manifest["labels_sha256"], sha256(self.labels))
        self.assertFalse(self.output.exists())

    def test_rejects_wrong_count_and_wrong_build(self):
        self.data["queries"].pop()
        write_json(self.labels, self.data)
        with self.assertRaisesRegex(ValueError, "24 queries"):
            inspect_release_inputs(self.index, self.labels)
        self.data["queries"].append({
            "id": "q24", "text": "Last test", "kind": "visual",
            "split": "test", "relevant": ["portfolio_nasa:00000"]})
        self.data["build_sha256"] = "invalid"
        write_json(self.labels, self.data)
        with self.assertRaisesRegex(ValueError, "another index"):
            inspect_release_inputs(self.index, self.labels)

    def test_release_executes_both_splits_and_preserves_sources(self):
        original = self.labels.read_bytes()
        calls = []
        def fake_evaluate(engine, labels, output, split, k):
            self.assertEqual(k, 5)
            calls.append(split)
            output.mkdir()
            write_json(output / "per_query.json", [{"query_id": "demo"}])
            (output / "report.md").write_text("Test report")
            return totals()
        with patch("scene_search.search.SearchEngine", return_value=object()), \
             patch("scene_search.evaluate.evaluate", side_effect=fake_evaluate):
            result = finish(self.index, self.labels, self.output, "cpu",
                            offline=True)
        self.assertEqual(calls, ["dev", "test"])
        self.assertEqual(result["status"], "LOCAL_ENGINEERING_CHECKS_PASS")
        self.assertEqual(result["accuracy_provenance"],
                         "AI_ASSISTED_WEAK_LABELS_ONLY")
        self.assertEqual(original, self.labels.read_bytes())
        self.assertIn("WEAK LABELS", (self.output / "RELEASE_SUMMARY.md").read_text())
        with zipfile.ZipFile(result["evidence_zip"]) as zf:
            self.assertIn("RELEASE_SUMMARY.md", zf.namelist())
            self.assertIn("dev/report.md", zf.namelist())
            self.assertIn("test/report.md", zf.namelist())
        with self.assertRaisesRegex(ValueError, "already exists"):
            finish(self.index, self.labels, self.output, "cpu")

    def test_failure_records_incomplete_status_without_source_edits(self):
        original = self.labels.read_bytes()
        with patch("scene_search.search.SearchEngine", side_effect=RuntimeError("missing cache")):
            with self.assertRaisesRegex(RuntimeError, "missing cache"):
                finish(self.index, self.labels, self.output, "cpu")
        self.assertEqual(original, self.labels.read_bytes())
        self.assertEqual(read_json(self.output / "RELEASE_STATUS.json")["status"],
                         "INCOMPLETE")
        self.assertFalse((self.output / "test").exists())

    def test_metrics_summary_is_accurately_scoped(self):
        summary = make_summary({
            "independently_verified": False,
            "index_build_sha256": "abc",
            "labels_sha256": "def",
        }, totals(), totals())
        self.assertIn("NOT independently human-verified", summary)
        self.assertIn("Provisional test (18 queries)", summary)
        self.assertIn("NOT VERIFIED IN THIS RUN", summary)
        self.assertIn("0.4000", summary)


if __name__ == "__main__":
    unittest.main()
