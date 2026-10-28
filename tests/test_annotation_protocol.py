"""Real file/CLI protocol tests; no videos, network, model weights or fabricated labels."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scene_search.annotations import finalize_labels, freeze_labels, init_labels
from scene_search.core import make_windows, read_json, write_json
from scene_search.evaluate import evaluate
from scene_search.statistics import paired_comparisons


class AnnotationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.windows = make_windows("fixture", 20)
        write_json(self.root / "build.json", {"fixture": True})
        write_json(self.root / "windows.json", self.windows)
        self.draft = self.root / "draft.json"
        self.plan = self.root / "plan.json"
        self.final = self.root / "final.json"
        init_labels(self.root, self.draft, count=3, dev_count=1)
        draft = read_json(self.draft)
        for q, text in zip(draft["queries"], ("red screen", "blue screen", "voice says hello")):
            q["text"] = text
        write_json(self.draft, draft)

    def review(self):
        draft = read_json(self.draft)
        for q in draft["queries"]:
            q["relevant"] = ["fixture:00000"]
            q["review"] = {"reviewed": True, "reviewer": "unit-test-fixture",
                           "evidence_note": "Synthetic protocol fixture, not a human annotation"}
        write_json(self.draft, draft)

    def test_complete_protocol_and_evaluation_uses_frozen_plan(self):
        freeze_labels(self.root, self.draft, self.plan)
        self.review()
        finalize_labels(self.root, self.draft, self.plan, self.final)
        self.assertIsNone(read_json(self.final)["independent_ground_truth"])
        engine = SimpleNamespace(root=self.root, windows=self.windows,
                                 rankings=lambda q, m: [("fixture:00000", 1)])
        with self.assertRaisesRegex(ValueError, "require --plan"):
            evaluate(engine, self.final, self.root / "bad")
        rows = evaluate(engine, self.final, self.root / "report", plan_path=self.plan,
                        compare_equal_rrf=True)
        self.assertEqual(len([r for r in rows if r["kind"] == "all"]), 4)
        self.assertEqual(read_json(self.root / "report/evidence.json")["evaluation_scope"],
                         "human_reviewed_self_reported")
        comparisons = read_json(self.root / "report/comparisons.json")
        self.assertTrue(all(r["mean_delta"] == 0 for r in comparisons["comparisons"]))

    def test_no_labels_or_predictions_in_frozen_plan(self):
        freeze_labels(self.root, self.draft, self.plan)
        for q in read_json(self.plan)["queries"]:
            self.assertEqual(set(q), {"id", "text", "kind", "split"})

    def test_freeze_rejects_normalized_reuse(self):
        previous = self.root / "old.json"
        write_json(previous, {"queries": [{"text": "  RED   ＳＣＲＥＥＮ "}]})
        with self.assertRaisesRegex(ValueError, "reuses"):
            freeze_labels(self.root, self.draft, self.plan, [previous])

    def test_changed_query_split_or_build_rejected(self):
        freeze_labels(self.root, self.draft, self.plan)
        self.review()
        original = read_json(self.draft)
        for key, value in (("text", "edited query"), ("split", "test"), ("kind", "mixed")):
            changed = read_json(self.draft)
            changed["queries"][0][key] = value
            write_json(self.draft, changed)
            with self.assertRaisesRegex(ValueError, "changed|both dev"):
                finalize_labels(self.root, self.draft, self.plan, self.final)
            write_json(self.draft, original)
        write_json(self.root / "build.json", {"different": True})
        with self.assertRaisesRegex(ValueError, "different build"):
            finalize_labels(self.root, self.draft, self.plan, self.final)

    def test_missing_review_and_tampered_plan_rejected(self):
        freeze_labels(self.root, self.draft, self.plan)
        self.review()
        draft = read_json(self.draft)
        draft["queries"][0]["review"]["reviewed"] = False
        write_json(self.draft, draft)
        with self.assertRaisesRegex(ValueError, "Human review"):
            finalize_labels(self.root, self.draft, self.plan, self.final)
        self.review()
        plan = read_json(self.plan)
        plan["queries"][0]["text"] = "edited"
        write_json(self.plan, plan)
        with self.assertRaisesRegex(ValueError, "plan hash"):
            finalize_labels(self.root, self.draft, self.plan, self.final)

    def test_missing_evidence_note_rejected(self):
        freeze_labels(self.root, self.draft, self.plan)
        self.review()
        draft = read_json(self.draft)
        draft["queries"][0]["review"]["evidence_note"] = " "
        write_json(self.draft, draft)
        with self.assertRaisesRegex(ValueError, "evidence_note"):
            finalize_labels(self.root, self.draft, self.plan, self.final)

    def test_no_overwrites(self):
        with self.assertRaises(FileExistsError):
            init_labels(self.root, self.draft)
        freeze_labels(self.root, self.draft, self.plan)
        with self.assertRaises(FileExistsError):
            freeze_labels(self.root, self.draft, self.plan)
        self.review()
        finalize_labels(self.root, self.draft, self.plan, self.final)
        before = self.final.read_bytes()
        with self.assertRaises(FileExistsError):
            finalize_labels(self.root, self.draft, self.plan, self.final)
        self.assertEqual(before, self.final.read_bytes())

    def test_cli_protocol_no_model_dependencies(self):
        repo = Path(__file__).resolve().parents[1]
        env = {**os.environ, "PYTHONPATH": str(repo / "src")}
        base = [sys.executable, "-m", "scene_search.cli"]
        commands = [
            ["freeze-labels", "--index", str(self.root), "--labels", str(self.draft),
             "--output", str(self.plan)],
            ["finalize-labels", "--index", str(self.root), "--labels", str(self.draft),
             "--plan", str(self.plan), "--output", str(self.final)],
        ]
        for i, command in enumerate(commands):
            if i:
                self.review()
            run = subprocess.run(base + command, env=env, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(read_json(self.final)["status"], "annotated")


class EvaluationAuditTests(unittest.TestCase):
    def test_bootstrap_is_paired_reproducible_and_signed(self):
        details = []
        for i, (a, b) in enumerate(((1, 0), (0, 1), (1, 0))):
            for mode, score in (("hybrid", a), ("visual", b)):
                details.append({"query_id": str(i), "mode": mode,
                                "recall@5": score, "hit@5": score, "mrr@5": score})
        result = paired_comparisons(details, 5)
        self.assertEqual(result, paired_comparisons(details, 5))
        for row in result["comparisons"]:
            self.assertAlmostEqual(row["mean_delta"], 1 / 3)
            self.assertEqual((row["wins"], row["losses"]), (2, 1))
            self.assertLessEqual(row["percentile_95_interval"][0], 0)
            self.assertGreaterEqual(row["percentile_95_interval"][1], 0)

    def test_evaluation_rejects_truncated_or_invalid_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from scene_search.core import sha256
            write_json(root / "build.json", {})
            labels = {"status": "annotated", "build_sha256": sha256(root / "build.json"),
                      "queries": [{"id": "q", "text": "red", "kind": "visual", "split": "test",
                                   "relevant": ["v:00000"]}]}
            write_json(root / "labels.json", labels)
            for batch in ([], [[("unknown", 1)]], [[("v:00000", 1), ("v:00000", .5)]]):
                engine = SimpleNamespace(root=root, windows=make_windows("v", 10),
                                         rankings_batch=lambda q, m: batch)
                with self.assertRaisesRegex(ValueError, "batch length|window IDs"):
                    evaluate(engine, root / "labels.json", root / "bad-report")
                self.assertFalse((root / "bad-report").exists())

    def test_unknown_provenance_and_single_query_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from scene_search.core import sha256
            write_json(root / "build.json", {})
            labels = {"status": "annotated", "build_sha256": sha256(root / "build.json"),
                      "queries": [{"id": "q", "text": "red", "kind": "visual", "split": "test",
                                   "relevant": ["v:00000"]}]}
            write_json(root / "labels.json", labels)
            engine = SimpleNamespace(root=root, windows=make_windows("v", 10),
                                     rankings=lambda q, m: [("v:00000", 1)])
            evaluate(engine, root / "labels.json", root / "report")
            self.assertEqual(read_json(root / "report/evidence.json")["evaluation_scope"],
                             "unverified_annotations")
            self.assertTrue(all(r["percentile_95_interval"] is None for r in
                                read_json(root / "report/comparisons.json")["comparisons"]))
