"""Optional real-model wiring check, NOT a quality benchmark.

Requires ffmpeg built with libflite, and downloadable/cached model weights.
Run from the project root after installing: python scripts/real_model_smoke.py
Generates its own synthetic color video and speech. No third-party media used.
"""
import subprocess
import tempfile
from pathlib import Path

from scene_search.core import write_json
from scene_search.pipeline import build
from scene_search.search import SearchEngine

with tempfile.TemporaryDirectory(prefix="scene-real-smoke-") as tmp:
    root = Path(tmp)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=320x240:r=10:d=8",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=10:d=8",
        "-f", "lavfi", "-i",
        "flite=text='This is a red screen. We are discussing the project deadline. Next there is a blue screen.':voice=slt",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v];[2:a]apad[a]",
        "-map", "[v]", "-map", "[a]", "-t", "16", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(root / "fixture.mp4")], check=True)
    write_json(root / "corpus.json", {"videos": [{"id": "smoke", "path": "fixture.mp4",
        "title": "Synthetic color and speech fixture", "source": "Generated locally by ffmpeg",
        "license": "Local testing only", "attribution": "Synthetic ffmpeg/flite fixture",
        "rights_confirmed": True}]})
    result = build(root / "corpus.json", root / "index", whisper_model="tiny", language="en")
    assert result["frames"] == 8, result
    assert result["speech_segments"] > 0, result
    engine = SearchEngine(root / "index")
    for mode in ("visual", "transcript", "hybrid"):
        results = engine.search("A red screen", mode)
        assert results and 0 <= results[0]["start"] < 16, results
        print(mode, results[0]["id"], results[0]["score"], flush=True)
    print("PASS: real model ingestion, persistence, and all search modes. NOT retrieval-quality evidence.")
