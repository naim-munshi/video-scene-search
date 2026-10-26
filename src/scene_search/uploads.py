"""Safe single-video staging for the **local-only** Streamlit importer.

Uploads are stored in ignored data/imports/ and are NOT indexed automatically.
Existing indexes and annotations remain untouched.
"""
import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path

from .core import write_json

MAX_UPLOAD_BYTES = 250 * 1024 * 1024


def validate_import_fields(name, size, title, source, license_text,
                           attribution, rights_confirmed):
    if not isinstance(name, str) or Path(name).suffix.lower() != ".mp4":
        raise ValueError("Upload an MP4 file (H.264/AAC recommended)")
    if not isinstance(size, int) or not 0 < size <= MAX_UPLOAD_BYTES:
        raise ValueError("Upload must be 250 MiB or less")
    for value, label in ((title, "Title"), (source, "Source"),
                         (license_text, "License"), (attribution, "Attribution")):
        if not isinstance(value, str) or not 0 < len(value.strip()) <= 400:
            raise ValueError(f"{label} must contain 1–400 characters")
    if rights_confirmed is not True:
        raise ValueError("Confirm that you have permission to process this video")


def verify_video(path):
    """Metadata/stream check, not a malware or redistribution-rights review."""
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=90)
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration", 0))
    streams = {s.get("codec_type") for s in data.get("streams", [])}
    if not math.isfinite(duration) or not 2 <= duration <= 7200:
        raise ValueError("Video must be 2 seconds to 2 hours long")
    if not {"video", "audio"} <= streams:
        raise ValueError("Uploaded video needs both video and audio streams")
    return duration


def stage_upload(upload, title, source, license_text, attribution,
                 rights_confirmed, root="data/imports"):
    size = int(getattr(upload, "size", 0))
    validate_import_fields(getattr(upload, "name", ""), size, title,
                           source, license_text, attribution, rights_confirmed)
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < size + 512 * 1024 * 1024:
        raise ValueError("Insufficient disk space for safe upload staging")
    folder = root / f"import_{uuid.uuid4().hex[:12]}"
    folder.mkdir(exist_ok=False)
    video = folder / "clip.mp4"
    try:
        written = 0
        upload.seek(0)
        with video.open("xb") as dest:
            while True:
                chunk = upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise ValueError("File exceeded maximum permitted upload size")
                dest.write(chunk)
        if written != size:
            raise ValueError("Incomplete uploaded video")
        duration = verify_video(video)
        payload = {"videos": [{
            "id": folder.name,
            "title": title.strip(),
            "path": "clip.mp4",
            "source": source.strip(),
            "license": license_text.strip(),
            "attribution": attribution.strip(),
            "rights_confirmed": True,
        }]}
        manifest = folder / "corpus.json"
        write_json(manifest, payload)
        return {
            "manifest": str(manifest),
            "output": str(Path("artifacts") / folder.name),
            "duration_seconds": round(duration, 1),
        }
    except Exception:
        shutil.rmtree(folder)
        raise
