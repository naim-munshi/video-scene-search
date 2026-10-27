"""Read-only local media decode preflight, NOT a Safari/browser sign-off.

Check every source clip from an already validated index by probing codecs and
decoding video at beginning/middle/end plus an audio excerpt.

python scripts/media_playback_preflight.py --index artifacts/portfolio-real-v2

No source, index or report is overwritten. Requires existing ffprobe/ffmpeg.
"""
import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from scene_search.core import read_json, write_json
from scripts.acceptance_check import audit_index


def sample_seconds(duration):
    if not math.isfinite(duration) or duration < 15:
        raise ValueError("Source clip must be at least 15 seconds")
    # Keep all timestamps within the actual file; avoid an EOF seek.
    return [5.0, duration / 2, max(5.0, duration - 15.0)]


def run_checked(argv, runner=subprocess.run):
    try:
        result = runner(
            argv, check=False, capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Media command unavailable or timed out: {argv[0]}") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"Media command failed ({argv[0]} exit={result.returncode}): "
            f"{result.stderr[:400]}")
    return result.stdout


def check_source(video, runner=subprocess.run):
    path = Path(video["path"]).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Source media missing for {video['id']}: {path}")
    output = run_checked([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name",
        "-of", "json", str(path)], runner=runner)
    try:
        probe = json.loads(output)
        duration = float(probe["format"]["duration"])
        streams = probe["streams"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ffprobe metadata for {video['id']}") from exc
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if not videos or not audios:
        raise ValueError(f"Missing video or audio stream for {video['id']}")
    if videos[0].get("codec_name") != "h264" or audios[0].get("codec_name") != "aac":
        raise ValueError(f"Expected browser-friendly H.264/AAC for {video['id']}")
    declared = float(video.get("duration", 0))
    if not math.isfinite(declared) or abs(declared - duration) > 2.0:
        raise ValueError(f"Duration mismatch for {video['id']}")
    timestamps = sample_seconds(duration)
    for seek in timestamps:
        run_checked([
            "ffmpeg", "-hide_banner", "-nostdin", "-v", "error",
            "-ss", f"{seek:.2f}", "-i", str(path), "-an",
            "-frames:v", "1", "-f", "null", "-"], runner=runner)
    run_checked([
        "ffmpeg", "-hide_banner", "-nostdin", "-v", "error",
        "-ss", f"{timestamps[1]:.2f}", "-i", str(path), "-vn",
        "-t", "2", "-f", "null", "-"], runner=runner)
    return {
        "video_id": video["id"],
        "duration_seconds": round(duration, 2),
        "video_codec": "h264",
        "audio_codec": "aac",
        "decoded_frame_checkpoints_seconds": [round(x, 2) for x in timestamps],
        "audio_decoded_seconds": 2,
        "status": "LOCAL_MEDIA_DECODE_PASS",
    }


def check_media(index, runner=subprocess.run):
    audit = audit_index(index)
    if audit["warnings"]:
        raise ValueError("; ".join(audit["warnings"]))
    corpus = read_json(Path(index) / "corpus.json")["videos"]
    if len(corpus) != 3:
        raise ValueError("Expected exactly three indexed portfolio sources")
    details = [check_source(video, runner=runner) for video in corpus]
    return {
        "status": "LOCAL_MEDIA_DECODE_PASS",
        "browser_playback_status": "NOT_VERIFIED",
        "human_audio_visual_review": "NOT_VERIFIED",
        "scope": "FFprobe metadata and FFmpeg start/middle/end decoding only; "
                 "does not exercise Safari video playback or search UI",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(details),
        "sources": details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/portfolio-real-v2")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = args.output
    if target is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = ROOT / "reports" / ("media-preflight-" + stamp + ".json")
    target = target.expanduser().resolve()
    try:
        if target.exists():
            raise ValueError(f"Refusing to overwrite {target}")
        result = check_media(args.index)
        write_json(target, result)
        print(json.dumps({"report": str(target), **result}, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        parser.exit(2, f"Local media decode preflight failed: {exc}\n")


if __name__ == "__main__":
    main()
