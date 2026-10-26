"""Query validation and evaluation batch reuse without heavy ML imports."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scene_search.query_worker import validate_query_batch
from scene_search.core import make_windows, sha256, write_json
from scene_search.evaluate import evaluate


class QueryBatchTests(unittest.TestCase):
    def test_validate_query_batch(self):
        validate_query_batch(["A red screen", "A voice talks"], "visual")
        for queries in ([], ["   "], ["a"] * 129, ["x" * 501]):
            with self.assertRaisesRegex(ValueError, "[Qq]uery"):
                validate_query_batch(queries, "visual")
        with self.assertRaisesRegex(ValueError, "Modality"):
            validate_query_batch(["word"], "hybrid")

    def test_evaluation_calls_each_modality_once_for_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "build.json", {"fixture": True})
            labels = {"status": "annotated", "build_sha256": sha256(root / "build.json"),
                      "queries": [
                          {"id": "q1", "text": "The red screen", "kind": "visual",
                           "split": "dev", "relevant": ["v:00000"]},
                          {"id": "q2", "text": "A voice talks", "kind": "speech",
                           "split": "dev", "relevant": ["v:00001"]}]}
            write_json(root / "labels.json", labels)
            calls = []
            def batch(queries, modality):
                calls.append((len(queries), modality))
                if modality == "visual":
                    return [[("v:00000", .9), ("v:00001", .2)] for _ in queries]
                return [[("v:00001", .9), ("v:00000", .1)] for _ in queries]
            engine = SimpleNamespace(root=root, windows=make_windows("v", 20),
                                     rankings_batch=batch)
            rows = evaluate(engine, root / "labels.json", root / "report", "dev", 5)
            self.assertEqual(calls, [(2, "visual"), (2, "transcript")])
            self.assertEqual(len([r for r in rows if r["kind"] == "all"]), 3)
            details = __import__("json").loads((root / "report/per_query.json").read_text())
            self.assertEqual(len(details), 6)
            self.assertIn("amortized_all_modes_seconds_including_batch_model_load",
                          details[0])


if __name__ == "__main__":
    unittest.main()
