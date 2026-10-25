"""Native decoder regression tests without loading actual FFmpeg native bindings."""
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from scene_search.pipeline import extract_frames


class FakeFrame:
    def __init__(self, time):
        self.time = time

    def to_image(self):
        return Image.new("RGB", (48, 32), (255, 0, 0))


class FakeContainer:
    def __init__(self, stream, frames):
        self.streams = SimpleNamespace(video=[stream])
        self.duration = None
        self._frames = frames

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def decode(self, stream):
        yield from self._frames


class FrameDecodeTests(unittest.TestCase):
    def test_pts_sampling_and_window_ids(self):
        stream = SimpleNamespace(duration=300, time_base=Fraction(1, 10),
                                 average_rate=Fraction(1, 1), start_time=0, frames=30)
        fake = SimpleNamespace(open=lambda *_a, **_kw: FakeContainer(
            stream, [FakeFrame(float(i)) for i in range(30)]))
        with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules, {"av": fake}):
            root = Path(td)
            (root / "frames").mkdir()
            duration, windows, rows = extract_frames("fake.mp4", "demo", root, 2, 10)
            self.assertAlmostEqual(duration, 30)
            self.assertEqual(len(windows), 3)
            self.assertEqual(len(rows), 15)
            self.assertEqual([r["timestamp"] for r in rows], list(range(0, 30, 2)))
            self.assertEqual([r["window_ids"][0] for r in rows[::5]],
                             ["demo:00000", "demo:00001", "demo:00002"])
            self.assertTrue(all((root / r["file"]).is_file() for r in rows))

    def test_truncated_video_is_rejected(self):
        stream = SimpleNamespace(duration=300, time_base=Fraction(1, 10),
                                 average_rate=Fraction(1, 1), start_time=0, frames=30)
        fake = SimpleNamespace(open=lambda *_a, **_kw: FakeContainer(
            stream, [FakeFrame(float(i)) for i in range(3)]))
        with tempfile.TemporaryDirectory() as td, patch.dict(sys.modules, {"av": fake}):
            root = Path(td)
            (root / "frames").mkdir()
            with self.assertRaisesRegex(ValueError, "ended early"):
                extract_frames("fake.mp4", "demo", root, 2, 10)


if __name__ == "__main__":
    unittest.main()
