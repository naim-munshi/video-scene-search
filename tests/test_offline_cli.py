"""Offline model selection must never suppress TLS certificate verification."""
import io
import os
import sys
import unittest
from unittest.mock import patch

from scene_search import cli, query_worker, search


class OfflineCLITests(unittest.TestCase):
    def test_offline_mode_changes_only_model_cache_switches(self):
        with patch.dict(os.environ, {
            "REQUESTS_CA_BUNDLE": "/some/trusted/roots.pem",
            "SSL_CERT_FILE": "/some/trusted/roots.pem",
            "HF_HUB_OFFLINE": "0",
            "TRANSFORMERS_OFFLINE": "0",
        }, clear=True):
            query_worker.enable_offline_cache()
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")
            self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], "/some/trusted/roots.pem")
            self.assertEqual(os.environ["SSL_CERT_FILE"], "/some/trusted/roots.pem")
            self.assertNotIn("CURL_CA_BUNDLE", os.environ)

    def test_search_offline_sets_flags_before_model_creation(self):
        def create_engine(*args, **kwargs):
            self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
            self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")
            fake = unittest.mock.Mock()
            fake.search.return_value = []
            return fake
        with patch.dict(os.environ, {"HF_HUB_OFFLINE": "0",
                                    "TRANSFORMERS_OFFLINE": "0"}, clear=False), \
             patch.object(search, "SearchEngine", side_effect=create_engine), \
             patch.object(sys, "argv", ["scene-search", "search", "moon mission",
                                      "--index", "ignored", "--offline"]), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            cli.main()
            self.assertIn("[]", output.getvalue())

    def test_evaluate_offline_sets_flags_before_model_creation(self):
        def create_engine(*args, **kwargs):
            self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
            fake = unittest.mock.Mock()
            return fake
        with patch.dict(os.environ, {"HF_HUB_OFFLINE": "0",
                                    "TRANSFORMERS_OFFLINE": "0"}, clear=False), \
             patch.object(search, "SearchEngine", side_effect=create_engine), \
             patch("scene_search.evaluate.evaluate", return_value=[]), \
             patch.object(sys, "argv", ["scene-search", "evaluate", "--index",
                                      "ignored", "--labels", "fake.json",
                                      "--output", "fake-report", "--offline"]), \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            cli.main()
            self.assertIn("[]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
