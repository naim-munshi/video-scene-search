"""Verify candidate prompts are useful but never treated as annotated evidence."""
import tempfile
import unittest
from pathlib import Path

from scene_search.core import read_json, sha256, write_json
from scripts.seed_portfolio_queries import QUERIES, seed_queries


class PortfolioQuerySeedTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root = Path(self.dir.name)
        self.index = root / "index"
        self.index.mkdir()
        self.labels = root / "draft.json"
        self.output = root / "suggestions.json"
        write_json(self.index / "build.json", {"fixture": True})
        write_json(self.index / "corpus.json", {"videos": [
            {"id": "portfolio_interview"},
            {"id": "portfolio_film"},
            {"id": "portfolio_nasa"},
        ]})
        self.draft = {
            "status": "draft",
            "build_sha256": sha256(self.index / "build.json"),
            "queries": [
                {"id": f"q{i:02d}", "text": "", "kind": ("visual", "speech", "mixed")[(i-1)%3],
                 "split": "dev" if i <= 6 else "test", "relevant": []}
                for i in range(1, 25)
            ],
        }
        write_json(self.labels, self.draft)

    def test_24_unique_query_ids_types_and_splits(self):
        self.assertEqual(len(QUERIES), 24)
        self.assertEqual([row[0] for row in QUERIES], [
            f"q{i:02d}" for i in range(1, 25)])
        self.assertEqual({r[3] for r in QUERIES}, {"visual", "speech", "mixed"})
        texts = [r[2].casefold() for r in QUERIES]
        self.assertEqual(len(set(texts)), 24)
        self.assertEqual({r[1] for r in QUERIES}, {
            "portfolio_interview", "portfolio_film", "portfolio_nasa",
        })

    def test_seeds_draft_but_not_relevance_labels(self):
        result = seed_queries(self.index, self.labels, self.output)
        seeded = read_json(self.output)
        self.assertEqual(result["dev"], 6)
        self.assertEqual(result["test"], 18)
        self.assertEqual(result["human_labeled"], 0)
        self.assertEqual(seeded["status"], "draft")
        self.assertEqual(len([q for q in seeded["queries"]
                              if q["split"] == "dev"]), 6)
        self.assertEqual(len([q for q in seeded["queries"]
                              if q["split"] == "test"]), 18)
        self.assertTrue(all(q["text"] and q["relevant"] == []
                            for q in seeded["queries"]))
        self.assertEqual(read_json(self.labels), self.draft)

    def test_preserves_manual_query_and_labels(self):
        self.draft["queries"][0].update({
            "text": "My already verified query",
            "kind": "visual", "relevant": ["portfolio_nasa:00011"],
        })
        write_json(self.labels, self.draft)
        seed_queries(self.index, self.labels, self.output)
        first = read_json(self.output)["queries"][0]
        self.assertEqual(first["text"], "My already verified query")
        self.assertEqual(first["kind"], "visual")
        self.assertEqual(first["relevant"], ["portfolio_nasa:00011"])

    def test_rejects_rewrite_or_incorrect_fingerprint(self):
        seed_queries(self.index, self.labels, self.output)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            seed_queries(self.index, self.labels, self.output)
        self.draft["build_sha256"] = "wrong"
        write_json(self.labels, self.draft)
        with self.assertRaisesRegex(ValueError, "does not match"):
            seed_queries(self.index, self.labels, self.output.parent / "fresh.json")

    def test_rejects_incorrect_dev_test_assignment(self):
        self.draft["queries"][6]["split"] = "dev"
        write_json(self.labels, self.draft)
        with self.assertRaisesRegex(ValueError, "Unexpected split"):
            seed_queries(self.index, self.labels, self.output)


if __name__ == "__main__":
    unittest.main()
