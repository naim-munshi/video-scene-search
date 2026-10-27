"""Small, dependency-free helpers for the local Streamlit interface."""
from pathlib import Path


def discover_indexes(artifacts="artifacts", preferred=None):
    """Return usable completed indexes; explicit SCENE_INDEX takes priority."""
    candidates = []
    if preferred is not None:
        candidates.append(Path(preferred).expanduser().resolve())
    root = Path(artifacts).expanduser().resolve()
    if root.is_dir():
        candidates += [p.parent for p in root.glob("*/build.json")]
    unique = {p for p in candidates if (p / "build.json").is_file()}
    head = (Path(preferred).expanduser().resolve()
            if preferred is not None else None)
    return sorted(unique, key=lambda p: (
        0 if p == head else 1,
        0 if "portfolio-real-v2" == p.name else
        1 if "portfolio-real" in p.name else
        2 if "demo" not in p.name else 3,
        p.name,
    ))


def is_synthetic(videos):
    """Detect deterministic synthetic fixtures without confusing real 3-video sets."""
    rows = list(videos.values()) if isinstance(videos, dict) else videos
    return bool(rows) and all(
        str(v.get("id", "")).startswith("demo_") and
        "synthetic" in str(v.get("title", "")).lower()
        for v in rows
    )


def readable_time(seconds):
    value = max(0, int(float(seconds)))
    hour, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return (f"{hour}:{minutes:02d}:{secs:02d}" if hour else
            f"{minutes:02d}:{secs:02d}")


def format_index(path):
    name = Path(path).name.replace("-", " ").replace("_", " ")
    prefix = "DEMO" if "demo" in Path(path).name.lower() else "LOCAL"
    return f"{prefix}  ·  {name}"


def preview_frames(videos, frames, index_root):
    """Pick a representative existing indexed frame for each video.

    Prefer a frame near 15% of the video duration, avoiding opening shots.
    Paths must stay within the trusted, completed index directory.
    """
    root = Path(index_root).resolve()
    previews = {}
    for video in videos:
        candidates = [f for f in frames if f.get("video_id") == video["id"]]
        if not candidates:
            previews[video["id"]] = None
            continue
        target = float(video.get("duration", 0)) * .15
        order = sorted(candidates, key=lambda frame:
                       abs(float(frame["timestamp"]) - target))
        image = None
        for frame in order:
            path = (root / frame["file"]).resolve()
            if path.is_relative_to(root) and path.is_file():
                image = path
                break
        previews[video["id"]] = image
    return previews



def playback_checkpoints(duration):
    """Three distinct start/middle/end checkpoints within a sourced MP4."""
    import math
    duration = float(duration)
    if not math.isfinite(duration) or duration < 40:
        raise ValueError("Browser playback checklist requires at least 40 seconds")
    return [
        ("Beginning", 5),
        ("Middle", int(duration // 2)),
        ("Near end", int(duration - 15)),
    ]


def browser_checklist_status(build_sha256, checks, video_ids):
    """Only a human can attest browser playback, not CI or model evaluation.

    *checks* maps video IDs to 3 named checkpoint booleans. An incomplete
    checklist is always NOT_VERIFIED, and even a completed checklist is
    self-attestation (not independent testing or proof of playback).
    """
    ids = list(video_ids)
    checkpoints = ("Beginning", "Middle", "Near end")
    complete = (len(ids) == 3 and len(set(ids)) == 3 and
                all(checks.get(vid, {}).get(step) is True
                    for vid in ids for step in checkpoints))
    return {
        "status": "USER_SELF_ATTESTED" if complete else "NOT_VERIFIED",
        "source": "manual_Streamlit_checkbox_self_attestation",
        "not_automated_safari_test": True,
        "independent_ground_truth_verified": False,
        "build_sha256": build_sha256,
        "expected_sources": ids,
        "checkpoints_per_video": list(checkpoints),
        "confirmed_checkpoints": sum(
            checks.get(vid, {}).get(step) is True
            for vid in ids for step in checkpoints),
        "required_checkpoints": 3 * len(ids),
    }
