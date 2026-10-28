import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scene_search.core import make_windows, read_json, sha256, write_json
from scene_search.review import (load_corpus, new_session, latest_labels, save_queries,
                                 freeze_session, save_review, finalize_session)


class ReviewFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.index = self.root / "index"
        self.index.mkdir()
        # Mechanical media-serving fixture only; no claim of playable video.
        self.media = self.root / "fixture.mp4"
        self.media.write_bytes(b"not-real-video-test-fixture")
        write_json(self.index / "corpus.json", {"videos": [
            {"id": "fixture", "title": "Software test fixture", "path": str(self.media), "duration": 20}]})
        write_json(self.index / "windows.json", make_windows("fixture", 20))
        write_json(self.index / "build.json", {"schema_version": 1, "files": {
            name: sha256(self.index / name) for name in ("corpus.json", "windows.json")}})
        self.session = self.root / "reviews/study-fixture"
        new_session(self.index, self.session, count=2, dev_count=1)

    def fill_queries(self):
        rows = [{"id": "q01", "text": "A red card", "kind": "visual", "split": "dev"},
                {"id": "q02", "text": "A voice says hello", "kind": "speech", "split": "test"}]
        save_queries(self.session, rows)


class ReviewSessionTests(ReviewFixture):
    def test_resume_snapshots_freeze_and_finalize(self):
        self.fill_queries()
        freeze_session(self.index, self.session)
        original = latest_labels(self.session).read_bytes()
        for qid in ("q01", "q02"):
            save_review(self.index, self.session, qid, ["fixture:00000"],
                        "test-fixture", "Mechanical test; not human evidence", True)
        self.assertEqual(len(list(self.session.glob("review-*.json"))), 3)
        self.assertEqual(read_json(latest_labels(self.session))["queries"][1]["review"]["reviewed"], True)
        self.assertEqual(sorted(self.session.glob("review-*.json"))[0].read_bytes(), original)
        finalize_session(self.index, self.session)
        self.assertEqual(read_json(self.session / "reviewed.json")["status"], "annotated")
        with self.assertRaisesRegex(ValueError, "finalized"):
            save_review(self.index, self.session, "q01", ["fixture:00000"], "test", "test", True)

    def test_blank_draft_can_be_saved_but_not_frozen(self):
        rows = [{k: q[k] for k in ("id", "text", "kind", "split")}
                for q in read_json(latest_labels(self.session))["queries"]]
        save_queries(self.session, rows)
        with self.assertRaises(ValueError):
            freeze_session(self.index, self.session)
        self.assertFalse((self.session / "plan.json").exists())

    def test_missing_review_or_unknown_windows_never_saved(self):
        self.fill_queries()
        freeze_session(self.index, self.session)
        before = latest_labels(self.session)
        for relevant, reviewer, note, confirmed in [
            ([], "test", "note", True), (["unknown"], "test", "note", True),
            (["fixture:00000"], "", "note", True), (["fixture:00000"], "test", "", True),
            (["fixture:00000"], "test", "note", False),
        ]:
            with self.assertRaises(ValueError):
                save_review(self.index, self.session, "q01", relevant, reviewer, note, confirmed)
        self.assertEqual(before, latest_labels(self.session))

    def test_integrity_and_frozen_fields(self):
        self.fill_queries()
        freeze_session(self.index, self.session)
        with self.assertRaisesRegex(ValueError, "frozen"):
            self.fill_queries()
        (self.index / "windows.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "integrity"):
            load_corpus(self.index)

    def test_new_session_never_replaces_existing(self):
        original = (self.session / "draft.json").read_bytes()
        with self.assertRaises(FileExistsError):
            new_session(self.index, self.session)
        self.assertEqual(original, (self.session / "draft.json").read_bytes())


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Requires Streamlit; exercised by UI CI")
class ReviewUITests(ReviewFixture):
    def launch(self):
        from streamlit.testing.v1 import AppTest
        self.env = patch.dict(os.environ, {"SCENE_INDEX": str(self.index),
                                          "SCENE_REVIEW_DIR": str(self.session.parent)})
        self.env.start()
        self.addCleanup(self.env.stop)
        return AppTest.from_file(str(Path(__file__).resolve().parents[1] / "review_app.py")).run(timeout=15)

    @staticmethod
    def item(elements, label):
        return next(item for item in elements if item.label == label)

    def test_ui_freeze_save_resume_finalize(self):
        self.fill_queries()
        app = self.launch()
        self.assertFalse(app.exception)
        self.item(app.button, "Save and freeze questions").click().run()
        self.assertFalse(app.exception)
        self.assertTrue((self.session / "plan.json").exists())
        for qid in ("q01", "q02"):
            self.item(app.selectbox, "Question to review").set_value(qid).run()
            self.item(app.multiselect, "All relevant windows across the collection").set_value(["fixture:00000"])
            self.item(app.text_input, "Reviewer alias").set_value("ui-test-fixture")
            self.item(app.text_area, "Evidence and timestamps").set_value("Test declaration only, not a human review")
            self.item(app.checkbox, "I watched the original source and checked every relevant window").check()
            self.item(app.button, "Save reviewed question").click().run()
            self.assertFalse(app.exception)
        # Simulate browser refresh/new session; saved records survive outside session_state.
        app = self.launch()
        self.assertFalse(app.exception)
        self.item(app.button, "Finalize human-review labels").click().run()
        self.assertFalse(app.exception)
        self.assertTrue((self.session / "reviewed.json").exists())
        self.assertEqual(len(app.code), 3)  # session folder + dev/test commands
        self.assertTrue(any("--compare-equal-rrf" in code.value for code in app.code))

    def test_ui_missing_media_blocks_completed_review(self):
        self.fill_queries()
        freeze_session(self.index, self.session)
        self.media.unlink()
        app = self.launch()
        self.item(app.multiselect, "All relevant windows across the collection").set_value(["fixture:00000"])
        self.item(app.text_input, "Reviewer alias").set_value("test")
        self.item(app.text_area, "Evidence and timestamps").set_value("test")
        self.item(app.checkbox, "I watched the original source and checked every relevant window").check()
        self.item(app.button, "Save reviewed question").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Restore all original videos" in error.value for error in app.error))
        self.assertFalse(read_json(latest_labels(self.session))["queries"][0]["review"]["reviewed"])
