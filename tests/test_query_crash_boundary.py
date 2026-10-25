"""Test that native failures in a query worker cannot crash the search host."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scene_search.search import _query_embedding_subprocess


class QueryCrashBoundaryTests(unittest.TestCase):
    def test_native_segmentation_fault_is_reported_as_exception(self):
        fake_np = SimpleNamespace()
        with patch.dict(sys.modules, {"numpy": fake_np}), \
             patch("scene_search.search.subprocess.run",
                   return_value=SimpleNamespace(returncode=-11)) as run:
            with self.assertRaisesRegex(RuntimeError, "exit"):
                _query_embedding_subprocess("project deadline", "visual", "mps")
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], sys.executable)
        self.assertIn("scene_search.query_worker", args[0])
        self.assertEqual(kwargs["env"]["OMP_NUM_THREADS"], "1")

    def test_worker_success_without_output_is_rejected(self):
        fake_np = SimpleNamespace()
        with patch.dict(sys.modules, {"numpy": fake_np}), \
             patch("scene_search.search.subprocess.run",
                   return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(RuntimeError, "no embedding"):
                _query_embedding_subprocess("project deadline", "transcript", "mps")


if __name__ == "__main__":
    unittest.main()
