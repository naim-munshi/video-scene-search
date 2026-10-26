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
