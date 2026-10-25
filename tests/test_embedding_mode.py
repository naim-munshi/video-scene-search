"""Dependency-free verification of mode selection and invalid arguments."""
import sys
import unittest
from unittest.mock import patch

from scene_search.pipeline import _isolate_visual


class VisualModeTests(unittest.TestCase):
    def test_macos_defaults_to_subprocess(self):
        self.assertTrue(_isolate_visual("auto", "darwin"))
        self.assertFalse(_isolate_visual("auto", "linux"))
        self.assertFalse(_isolate_visual("auto", "win32"))

    def test_explicit_mode_overrides_platform(self):
        self.assertTrue(_isolate_visual("subprocess", "linux"))
        self.assertFalse(_isolate_visual("in-process", "darwin"))

    def test_invalid_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, "embedding_mode"):
            _isolate_visual("maybe", "darwin")


if __name__ == "__main__":
    unittest.main()
