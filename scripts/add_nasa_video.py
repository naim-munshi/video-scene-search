"""Create a three-video corpus from the existing two-video manifest and a local NASA MP4.

Does not download, transcode, copy or modify existing videos or labels.
Run before scene-search extend:
  python scripts/add_nasa_video.py
  python scripts/add_nasa_video.py --source ~/Downloads/nasa_apollo15.mp4
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scene_search.core import read_json, write_json
from scene_search.pipeline import load_manifest
from scripts.prepare_portfolio_videos import VIDEOS, manifest_entry, probe


def find_nasa_source(data_root, explicit=None):
    data_root = Path(data_root).expanduser().resolve()
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.is_file():
            raise ValueError(f"NASA source not found: {candidate}")
        return candidate
    home = Path.home()
    candidates = [
        data_root / "videos" / "portfolio_nasa.mp4",
        data_root / "videos" / "nasa_apollo15.mp4",
        home / "nasa_apollo15.mp4",
        home / "Downloads" / "nasa_apollo15.mp4",
    ]
    return next((p for p in candidates if p.is_file()), None)


def create_three_video_manifest(data_root, source=None, output=None):
    data_root = Path(data_root).expanduser().resolve()
    original = data_root / "portfolio-corpus.json"
    if not original.is_file():
        raise ValueError(f"Two-video manifest not found: {original}")
    prior = read_json(original)
    rows = prior.get("videos") if isinstance(prior, dict) else None
    if not isinstance(rows, list) or len(rows) != 2 or (
        {v.get("id") for v in rows if isinstance(v, dict)}
        != {"portfolio_interview", "portfolio_film"}
    ):
        raise ValueError("Expected exactly the indexed interview and film in base manifest")
    load_manifest(original)  # Existing rights and files must remain valid.
    source = find_nasa_source(data_root, source)
    if source is None:
        raise ValueError("NASA MP4 not found; use --source /path/to/nasa_apollo15.mp4")
    duration = probe(source)
    entry = manifest_entry(VIDEOS["nasa"])
    entry["path"] = os.path.relpath(source, start=data_root)
    merged = {"videos": [*rows, entry]}
    output = (Path(output).expanduser().resolve() if output else
              data_root / "portfolio-corpus-3.json")
    if output.parent != data_root:
        raise ValueError("Place the three-video manifest in the same data directory")
    if output.exists():
        if read_json(output) != merged:
            raise ValueError(f"Manifest already exists with different inputs: {output}")
    else:
        write_json(output, merged)
    load_manifest(output)
    return {"manifest": str(output), "nasa_file": str(source),
            "nasa_duration_seconds": round(duration, 2),
            "videos": 3,
            "note": "No media copied or downloaded. Existing two-video index preserved."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--source", help="Exact path to already downloaded NASA MP4")
    parser.add_argument("--output", help="Three-video JSON name under data/")
    args = parser.parse_args()
    try:
        print(json.dumps(create_three_video_manifest(args.data_root, args.source, args.output),
                         indent=2))
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"NASA manifest creation failed: {exc}\n")


if __name__ == "__main__":
    main()
