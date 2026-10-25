"""Dependency-free regression of safe query-mode selection and CLI worker contract."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scene_search.search import _should_isolate_query
from scene_search.query_worker import select_device


class QuerySafetyTests(unittest.TestCase):
    def test_macos_default_is_isolated(self):
        self.assertTrue(_should_isolate_query("auto", "darwin"))
        self.assertFalse(_should_isolate_query("auto", "linux"))

    def test_explicit_modes(self):
        self.assertTrue(_should_isolate_query("subprocess", "linux"))
        self.assertFalse(_should_isolate_query("in-process", "darwin"))
        with self.assertRaisesRegex(ValueError, "embedding_mode"):
            _should_isolate_query("bogus", "darwin")

    def test_mps_autoselect(self):
        fake = SimpleNamespace(
            backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
            cuda=SimpleNamespace(is_available=lambda: False))
        self.assertEqual(select_device("auto", fake), "mps")
        self.assertEqual(select_device("cpu", fake), "cpu")
        self.assertEqual(select_device("mps", fake), "mps")
        with self.assertRaisesRegex(RuntimeError, "CUDA"):
            select_device("cuda", fake)

    def test_cpu_fallback_for_non_mps(self):
        fake = SimpleNamespace(
            backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
            cuda=SimpleNamespace(is_available=lambda: False))
        self.assertEqual(select_device("auto", fake), "cpu")
        with self.assertRaisesRegex(RuntimeError, "MPS"):
            select_device("mps", fake)


if __name__ == "__main__":
    unittest.main()
