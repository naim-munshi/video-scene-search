"""Validate Git-tracked media/privacy guard using pure Python."""
import unittest
from scripts.check_repository_hygiene import forbidden_tracked_paths


class GitRepositoryHygieneTests(unittest.TestCase):
    def test_rejects_private_or_binary_artifacts(self):
        paths = [
            "data/videos/interview.mp4",
            "artifacts/index/visual.faiss",
            "evaluation/labels.json",
            "reports/dev/metrics.csv",
            "docs/recording.webm",
            "checkpoint.safetensors",
            "secrets.pem",
            ".env",
            ".env.production",
            "nested/.env.local",
            ".DS_Store",
        ]
        self.assertEqual(forbidden_tracked_paths(paths), sorted(paths))

    def test_safe_repository_files_and_example_config(self):
        paths = [
            "README.md",
            "src/scene_search/core.py",
            "docs/ARCHITECTURE.md",
            "docs/DEMO_RECORDING.md",
            ".env.example",
            ".github/workflows/tests.yml",
            "examples/corpus.json",
            "tests/test_core.py",
        ]
        self.assertEqual(forbidden_tracked_paths(paths), [])

    def test_mixed_paths_are_deterministic(self):
        paths = ["model.ckpt", "model.ckpt", "README.md"]
        self.assertEqual(forbidden_tracked_paths(paths), ["model.ckpt"])


if __name__ == "__main__":
    unittest.main()
