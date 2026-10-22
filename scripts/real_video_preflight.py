"""Validate local video metadata and recorded permission before expensive indexing.

The script cannot verify the truth of license claims, audio intelligibility,
participant consent, or whether all footage can lawfully be redistributed.
It intentionally does not upload or copy video files.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def preflight(manifest, min_seconds=600, max_seconds=1200):
    from scene_search.pipeline import load_manifest

    if not (0 < min_seconds <= max_seconds):
        raise ValueError("Invalid duration range")
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe missing; install ffmpeg first")
    videos = load_manifest(manifest)
    rows, issues = [], []
    if not 2 <= len(videos) <= 3:
        issues.append("Portfolio acceptance expects 2-3 videos")
    for v in videos:
        completed = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                    "format=duration:stream=codec_type,codec_name,avg_frame_rate,r_frame_rate",
                                    "-of", "json", v["path"]], capture_output=True, text=True, check=True)
        info = json.loads(completed.stdout)
        streams = info.get("streams", [])
        visual = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(info.get("format", {}).get("duration", 0))
        warnings = []
        if not min_seconds <= duration <= max_seconds:
            issues.append(f"{v['id']}: expected {min_seconds:g}-{max_seconds:g}s, got {duration:.1f}s")
        if visual is None:
            issues.append(f"{v['id']}: no video stream")
        if audio is None:
            issues.append(f"{v['id']}: no audio stream to transcribe")
        if visual and visual.get("r_frame_rate") != visual.get("avg_frame_rate"):
            warnings.append("Frame rates differ; inspect for variable frame rate before ingestion")
        if visual and visual.get("codec_name") != "h264":
            warnings.append("H.264 is recommended for browser playback")
        rows.append({"id": v["id"], "duration_seconds": round(duration, 2),
                     "video_codec": visual.get("codec_name") if visual else None,
                     "audio_codec": audio.get("codec_name") if audio else None,
                     "warnings": warnings})
    return {"passed": not issues, "videos": rows, "issues": issues,
            "caveat": "Metadata check only; license and speech quality require human review"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="examples/corpus.json")
    parser.add_argument("--min-seconds", type=float, default=600)
    parser.add_argument("--max-seconds", type=float, default=1200)
    args = parser.parse_args()
    try:
        result = preflight(args.manifest, args.min_seconds, args.max_seconds)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Preflight error: {exc}\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        parser.exit(1)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    main()
