import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scene_search.core import (aggregate_rank, fuse, hybrid_fuse, hybrid_weights, make_windows, metrics,
                               overlap, sha256, validate_labels, write_json)
from scene_search.evaluate import evaluate
from scene_search.pipeline import load_manifest


class CoreTests(unittest.TestCase):
    def test_tail_window_and_unique_ids(self):
        windows = make_windows("v", 21)
        self.assertEqual([(w["start"], w["end"]) for w in windows], [(0, 10), (10, 20), (20, 21)])
        self.assertEqual(len({w["id"] for w in windows}), 3)

    def test_exact_boundary_no_extra_window(self):
        self.assertEqual(len(make_windows("v", 20)), 2)

    def test_invalid_duration(self):
        for duration in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                make_windows("v", duration)

    def test_nonoverlapping_boundary(self):
        self.assertEqual(overlap(0, 10, 10, 20), 0)

    def test_aggregate_repeated_frames_and_crossing_segment(self):
        rows = [{"window_ids": ["a"]}, {"window_ids": ["a", "b"]}]
        self.assertEqual(aggregate_rank([.7, .9], [0, 1], rows), [("a", .9), ("b", .9)])

    def test_invalid_faiss_row_is_ignored(self):
        self.assertEqual(aggregate_rank([0], [-1], []), [])

    def test_rrf_consensus(self):
        result = fuse([("a", .99), ("b", .5)], [("b", .1), ("c", .09)])
        self.assertEqual(result[0][0], "b")

    def test_hybrid_prioritizes_speech_only_query_without_losing_visual_fallback(self):
        visual = [("wrong", 0.8), ("right", 0.7)]
        transcript = [("right", 0.9), ("wrong", 0.2)]
        self.assertEqual(hybrid_fuse("A voice talks about the deadline", visual, transcript)[0][0],
                         "right")
        self.assertEqual(hybrid_fuse("A voice talks about the deadline", visual, [])[0][0],
                         "wrong")

    def test_hybrid_keeps_visual_priority_when_visible_only(self):
        visual = [("visible", 0.8), ("speech", 0.7)]
        transcript = [("speech", 0.9), ("visible", 0.2)]
        self.assertEqual(hybrid_fuse("The red screen", visual, transcript)[0][0], "visible")

    def test_mixed_query_keeps_equal_weight_fusion(self):
        visual = [("a", 1.0), ("b", 0.5)]
        transcript = [("b", 1.0), ("c", 0.5)]
        self.assertEqual(hybrid_weights("A red screen while narrator talks"), (1.0, 1.0))
        self.assertEqual(hybrid_fuse("A red screen while narrator talks", visual, transcript),
                         fuse(visual, transcript))

    def test_visual_scene_language_routes_to_visual_evidence(self):
        visual_queries = (
            "The interview opens with two seated men and name captions visible.",
            "A robot stands near a building.",
            "Two people appear in a close-up shot.",
            "A futuristic machine is shown outdoors.",
        )
        for query in visual_queries:
            with self.subTest(query=query):
                self.assertEqual(hybrid_weights(query), (1.0, 0.35))
        speech_query = "A narrator describes the Apollo mission."
        self.assertEqual(hybrid_weights(speech_query), (0.2, 1.0))
        mixed_query = "A seated astronaut explains the instrument controls."
        self.assertEqual(hybrid_weights(mixed_query), (1.0, 1.0))

    def test_undetermined_query_uses_transcript_prior(self):
        visual = [("x", 0.9), ("right", 0.3)]
        transcript = [("right", 0.9), ("x", 0.3)]
        self.assertEqual(hybrid_fuse("project deadline", visual, transcript)[0][0], "right")

    def test_invalid_rrf_weights_rejected(self):
        for a, b in ((-1, 1), (float("nan"), 1), (0, 0)):
            with self.assertRaises(ValueError):
                fuse([], [], visual_weight=a, transcript_weight=b)

    def test_rrf_missing_speech(self):
        self.assertEqual([r[0] for r in fuse([("a", 1), ("b", .5)], [])], ["a", "b"])

    def test_recall_not_hit_rate(self):
        result = metrics(["a", "x"], ["a", "b"])
        self.assertEqual(result["recall@5"], .5)
        self.assertEqual(result["hit@5"], 1)

    def test_duplicate_prediction_no_credit(self):
        self.assertEqual(metrics(["a", "a"], ["a", "b"])["recall@5"], .5)

    def test_mrr(self):
        self.assertEqual(metrics(["x", "a"], ["a"])["mrr@5"], .5)

    def test_empty_ground_truth_rejected(self):
        with self.assertRaises(ValueError):
            metrics([], [])

    def labels(self):
        return {"status": "annotated", "queries": [{"id": "q1", "text": "a person talking",
                "kind": "visual", "split": "test", "relevant": ["v:00000"]}]}

    def test_draft_rejected(self):
        with self.assertRaises(ValueError):
            validate_labels({"status": "draft"}, [])

    def test_unknown_label_rejected(self):
        with self.assertRaises(ValueError):
            validate_labels(self.labels(), [])

    def test_duplicate_query_across_split_rejected(self):
        labels = self.labels()
        labels["queries"].append({**labels["queries"][0], "id": "q2", "split": "dev"})
        with self.assertRaises(ValueError):
            validate_labels(labels, make_windows("v", 10))

    def test_invalid_manifest_shapes_rejected_before_native_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "manifest.json"
            for data in ([], {"videos": "not a list"}, {"videos": [None]}):
                write_json(path, data)
                with self.assertRaises(ValueError):
                    load_manifest(path)
            write_json(path, {"videos": [{"id": "clip", "title": "ok",
                "source": "self", "license": "owned", "attribution": "author",
                "rights_confirmed": True}]})
            with self.assertRaisesRegex(ValueError, "video path"):
                load_manifest(path)

    def test_out_of_range_faiss_rows_ignored(self):
        self.assertEqual(aggregate_rank([0.9], [12], [{"window_ids": ["valid"]}]), [])

    def test_rights_confirmation_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            write_json(path, {"videos": [{"id": "a", "title": "t", "source": "s", "license": "l",
                "attribution": "a", "path": "x.mp4", "rights_confirmed": False}]})
            with self.assertRaisesRegex(ValueError, "Confirm"):
                load_manifest(path)

    def test_evaluation_reports_real_supplied_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "build.json", {"fixture": True})
            labels = self.labels()
            labels["build_sha256"] = sha256(root / "build.json")
            write_json(root / "labels.json", labels)
            engine = SimpleNamespace(root=root, windows=make_windows("v", 20),
                rankings=lambda query, mode: [("v:00000", .9)] if mode == "visual" else [("v:00001", .8)])
            result = evaluate(engine, root / "labels.json", root / "report", k=1)
            all_rows = {r["mode"]: r for r in result if r["kind"] == "all"}
            self.assertEqual(all_rows["visual"]["recall@1"], 1)
            self.assertEqual(all_rows["transcript"]["recall@1"], 0)
            self.assertTrue((root / "report" / "report.md").is_file())
            with self.assertRaisesRegex(ValueError, "directory exists"):
                evaluate(engine, root / "labels.json", root / "report")

    def test_ai_assisted_labels_must_disclose_weak_ground_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "build.json", {"fixture": True})
            labels = self.labels()
            labels.update({
                "build_sha256": sha256(root / "build.json"),
                "status": "annotated",
                "annotation_method": "assistant_assisted_contact_sheets_and_asr",
                "human_verified": False,
                "independent_ground_truth": False,
                "evaluation_scope": "weak_label_sanity_check_only_not_real_world_accuracy",
            })
            write_json(root / "labels.json", labels)
            engine = SimpleNamespace(root=root, windows=make_windows("v", 20),
                rankings=lambda query, mode: [("v:00000", .9)])
            evaluate(engine, root / "labels.json", root / "report", k=1)
            from scene_search.core import read_json
            record = read_json(root / "report" / "evidence.json")
            self.assertEqual(record["evaluation_scope"], "weak_label_sanity_check_only")
            self.assertEqual(record["human_verified"], False)
            self.assertEqual(record["independent_ground_truth"], False)
            report = (root / "report" / "report.md").read_text()
            self.assertIn("AI-ASSISTED WEAK LABELS ONLY", report)
            self.assertIn("not independently human-verified", report)

    def test_report_explains_recall_ceiling_for_10_relevant_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "build.json", {"fixture": True})
            windows = make_windows("v", 100)
            labels = {"status": "annotated",
                      "build_sha256": sha256(root / "build.json"),
                      "queries": [{"id": "q02",
                                   "text": "A seated person beside the rover",
                                   "kind": "visual", "split": "dev",
                                   "relevant": [w["id"] for w in windows]}]}
            write_json(root / "labels.json", labels)
            engine = SimpleNamespace(
                root=root, windows=windows,
                rankings=lambda text, mode: [(w["id"], 1.0)
                                             for w in windows[:5]])
            evaluate(engine, root / "labels.json", root / "report",
                     split="dev", k=5)
            report = (root / "report" / "report.md").read_text()
            self.assertIn("maximum Recall@5 = 0.5000", report)
            from scene_search.core import read_json
            details = read_json(root / "report" / "per_query.json")
            self.assertTrue(all(d["max_possible_recall_at_k"] == 0.5
                                for d in details))

    def test_stale_build_labels_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "build.json", {})
            labels = self.labels()
            labels["build_sha256"] = "old"
            write_json(root / "labels.json", labels)
            engine = SimpleNamespace(root=root, windows=make_windows("v", 10))
            with self.assertRaisesRegex(ValueError, "different build"):
                evaluate(engine, root / "labels.json", root / "report")


if __name__ == "__main__":
    unittest.main()
