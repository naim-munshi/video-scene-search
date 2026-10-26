"""Run all three retrieval modes against an existing or fresh synthetic demo.

A *functional smoke test*, never a retrieval-quality benchmark. On macOS the
models run in isolated MPS-capable workers, not with FFmpeg's optional flite
speech filter. No user video is uploaded or modified.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scene_search.search import SearchEngine
from scene_search.pipeline import build


def smoke(index, device):
    engine = SearchEngine(index, device=device)
    results = {}
    for mode in ("visual", "transcript", "hybrid"):
        ranked = engine.search("A red screen", mode=mode, k=3)
        if not ranked:
            raise RuntimeError(f"No results for {mode}; check index/transcription")
        if any(not 0 <= row["start"] < row["end"] for row in ranked):
            raise RuntimeError(f"Invalid timestamps for {mode}")
        results[mode] = [
            {"window_id": r["id"], "start": r["start"], "end": r["end"]}
            for r in ranked
        ]
    return {"status": "PASS", "index": str(Path(index).resolve()), "device": device,
            "results": results,
            "scope": "Synthetic model wiring only; not real-scene retrieval accuracy"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/demo-index-isolated")
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--generate", action="store_true",
                        help="Generate a fresh 3-video demo and ingest it in a temporary directory")
    args = parser.parse_args()
    try:
        if args.generate:
            from synthetic_demo import generate
            with tempfile.TemporaryDirectory(prefix="scene-full-smoke-") as td:
                root = Path(td)
                manifest = generate(root)
                # For a full smoke test select an explicit Metal device on macOS,
                # or cpu otherwise; 'auto' is for query device selection.
                device = args.device
                if device == "auto":
                    import torch
                    device = "mps" if torch.backends.mps.is_available() else "cpu"
                build(manifest, root / "index", whisper_model="tiny",
                      language="en", device=device)
                outcome = smoke(root / "index", device)
                outcome["generated_video_count"] = 3
        else:
            outcome = smoke(args.index, args.device)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, f"Smoke test failed: {exc}\n")
    print(json.dumps(outcome, indent=2))


if __name__ == "__main__":
    main()
