"""Review a local scene-search index without uploading or modifying video data.

Examples:
  python scripts/acceptance_check.py --index artifacts/demo-index-isolated
  python scripts/acceptance_check.py --index artifacts/demo-index-isolated --query "project deadline" --device mps
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scene_search.core import read_json, sha256
from scene_search.pipeline import VISUAL_MODEL, TEXT_MODEL


REQUIRED = {
    "corpus.json", "windows.json", "frames.json", "segments.json",
    "visual.faiss",
}


def audit_index(index):
    """Pure-Python integrity/consistency audit; does not load untrusted FAISS data."""
    root = Path(index).expanduser().resolve()
    build = root / "build.json"
    if not build.is_file():
        raise ValueError(f"No completed index at {root}; build.json missing")
    meta = read_json(build)
    if meta.get("schema_version") != 1:
        raise ValueError("Unsupported index schema")
    if meta.get("visual_model") != VISUAL_MODEL or meta.get("text_model") != TEXT_MODEL:
        raise ValueError("Unexpected embedding models")
    files = meta.get("files")
    if not isinstance(files, dict) or not REQUIRED <= set(files):
        raise ValueError("Build manifest missing required files")
    if not all(isinstance(k, str) and isinstance(v, str) and len(v) == 64
               for k, v in files.items()):
        raise ValueError("Invalid build file manifest")
    for rel, expected in files.items():
        path = (root / rel).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Invalid index file path: {rel}")
        if sha256(path) != expected:
            raise ValueError(f"File integrity mismatch: {rel}")

    videos = read_json(root / "corpus.json")["videos"]
    windows = read_json(root / "windows.json")
    frames = read_json(root / "frames.json")
    segments = read_json(root / "segments.json")
    if not videos or not windows or not frames:
        raise ValueError("Index must include videos, windows and sampled frames")
    video_ids = [v["id"] for v in videos]
    if len(video_ids) != len(set(video_ids)):
        raise ValueError("Duplicate video IDs")
    duration_by_video = {v["id"]: float(v["duration"]) for v in videos}
    if any(not math.isfinite(x) or x <= 0 for x in duration_by_video.values()):
        raise ValueError("Invalid video duration")
    window_by_id = {}
    for w in windows:
        if w["id"] in window_by_id or w["video_id"] not in duration_by_video:
            raise ValueError("Duplicate window ID or unknown video ID")
        start, end = float(w["start"]), float(w["end"])
        if not (math.isfinite(start) and math.isfinite(end) and
                0 <= start < end <= duration_by_video[w["video_id"]] + .5):
            raise ValueError("Invalid search window timestamps")
        window_by_id[w["id"]] = w
    for kind, rows in (("frame", frames), ("transcript", segments)):
        for item in rows:
            vid = item.get("video_id")
            if vid not in duration_by_video or not item.get("window_ids"):
                raise ValueError(f"Invalid {kind} video or window mapping")
            for window_id in item["window_ids"]:
                if window_id not in window_by_id or window_by_id[window_id]["video_id"] != vid:
                    raise ValueError(f"Unknown/cross-video {kind} window reference")
            if kind == "frame":
                frame_path = (root / item["file"]).resolve()
                if (not frame_path.is_relative_to(root) or
                    not frame_path.is_file() or
                    not 0 <= float(item["timestamp"]) <= duration_by_video[vid] + .5):
                    raise ValueError("Invalid sampled frame")
            else:
                start, end = float(item["start"]), float(item["end"])
                if (not item.get("text", "").strip() or
                    not 0 <= start < end <= duration_by_video[vid] + .5):
                    raise ValueError("Invalid speech segment")
    if bool(segments) != ("transcript.faiss" in files):
        raise ValueError("Transcript FAISS presence does not match segments")
    missing_sources = [v["id"] for v in videos if not Path(v["path"]).is_file()]
    return {
        "status": "metadata_integrity_passed",
        "index": str(root),
        "build_sha256": sha256(build),
        "video_count": len(videos),
        "window_count": len(windows),
        "sampled_frames": len(frames),
        "speech_segments": len(segments),
        "warnings": ([f"Source videos unavailable locally: {', '.join(missing_sources)}"]
                     if missing_sources else []),
        "scope": "File hashes, cross-references and timestamps only; "
                 "not model accuracy, browser playback or FAISS-native safety",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/demo-index-isolated")
    parser.add_argument("--query", default=None,
                        help="Optionally exercise all three retrieval modes (loads local FAISS and model workers)")
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--output", type=Path, help="Optional NEW JSON output; never overwrite")
    args = parser.parse_args()
    try:
        report = audit_index(args.index)
        if args.query is not None:
            from scene_search.search import SearchEngine
            engine = SearchEngine(args.index, device=args.device)
            report["smoke_query"] = args.query
            report["smoke_results"] = {}
            for mode in ("visual", "transcript", "hybrid"):
                ranked = engine.search(args.query, mode, k=3)
                report["smoke_results"][mode] = [
                    {"window_id": r["id"], "start": r["start"], "end": r["end"]}
                    for r in ranked
                ]
            report["scope"] += "; smoke retrieval checks functionality, not relevance"
        if args.output:
            if args.output.exists():
                raise ValueError(f"Refusing to overwrite {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        parser.exit(2, f"Acceptance check failed: {exc}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
