"""Download three license-documented videos and prepare a local corpus.

The media comes directly from Wikimedia Commons or the NASA archival listing.
Only the small source code is committed; downloads, transcripts and indexes
stay in ignored data/. Review third-party rights before republishing footage.

Examples:
    python scripts/prepare_portfolio_videos.py --plan
    python scripts/prepare_portfolio_videos.py --only interview film --local-only
    python scripts/prepare_portfolio_videos.py --only interview nasa
    python scripts/prepare_portfolio_videos.py
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = {
    "interview": {
        "id": "portfolio_interview",
        "title": "Technology interview: Steve Wozniak",
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Interview_with_Steve_Wozniak.webm",
        "source_page": "https://commons.wikimedia.org/wiki/File:Interview_with_Steve_Wozniak.webm",
        "source": "Wikimedia Commons, imported from ConversationEDU",
        "license": "CC BY 3.0 Unported",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "attribution": "ConversationEDU; original source and CC BY 3.0 license at Wikimedia Commons",
        "duration_seconds": 888,
        "input_size_mb": 160.11,
    },
    "nasa": {
        "id": "portfolio_nasa",
        "title": "NASA: Aeronautics and Space Report (Apollo 15)",
        "url": "https://apollo15hub.org/files/original/6fc0646cf1fab4ba948c44826a099ed2.mp4",
        "source_page": "https://apollo15hub.org/items/show/176",
        "source": "NASA (1971) via Emory Apollo 15 Learning Hub",
        "license": "Public Domain, per Apollo 15 Learning Hub source listing",
        "license_url": "https://apollo15hub.org/items/show/176",
        "attribution": "NASA; via the Apollo 15 Learning Hub, Emory Center for Digital Scholarship",
        "duration_seconds": 887,
        "input_size_mb": None,
    },
    "film": {
        "id": "portfolio_film",
        "title": "Tears of Steel (Blender Open Movie)",
        "url": "https://upload.wikimedia.org/wikipedia/commons/c/cb/Tears_of_Steel_1080p.webm",
        "source_page": "https://commons.wikimedia.org/wiki/File:Tears_of_Steel_1080p.webm",
        "source": "Blender Foundation / Mango Open Movie",
        "license": "CC BY 3.0 Unported",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "attribution": "(CC) Blender Foundation | mango.blender.org; retain film credits",
        "duration_seconds": 734,
        "input_size_mb": 544.88,
    },
}
USER_AGENT = "VideoSceneSearchPortfolio/0.1 (https://github.com/naim-munshi/video-scene-search; local education)"

# Aliases used by the direct curl commands in the user-facing quickstart.
# Never delete user-downloaded originals; conversion outputs separate MP4s.
LOCAL_SOURCE_NAMES = {
    "interview": ("interview.webm", "Interview_with_Steve_Wozniak.webm"),
    "film": ("tears_of_steel.webm", "Tears_of_Steel_1080p.webm"),
    "nasa": ("nasa_apollo15.mp4",),
}


def find_local_source(key, videos_dir):
    """Prefer a validated, explicitly named existing local download."""
    if key not in LOCAL_SOURCE_NAMES:
        raise ValueError("Unknown video source")
    for name in LOCAL_SOURCE_NAMES[key]:
        candidate = Path(videos_dir) / name
        if candidate.is_file() and candidate.stat().st_size >= 100_000:
            return candidate
    return None


def manifest_entry(item):
    return {
        "id": item["id"],
        "title": item["title"],
        "path": f"videos/{item['id']}.mp4",
        "source": item["source_page"],
        "license": f"{item['license']}; {item['license_url']}",
        "attribution": item["attribution"],
        "rights_confirmed": True,
    }


def make_manifest(selected):
    """Manifest asserts only the published media licenses reviewed at sources.

    Rights in external music, likenesses, trademarks, etc. may need separate
    review before redistribution; this flag is not a legal clearance.
    """
    if not selected or len(selected) > 3 or len(set(selected)) != len(selected):
        raise ValueError("Select one to three different corpus videos")
    if any(key not in VIDEOS for key in selected):
        raise ValueError("Unknown video identifier")
    return {"videos": [manifest_entry(VIDEOS[key]) for key in selected]}


def download(url, destination, max_bytes=900_000_000):
    """Download a curated static URL to a temporary file, with a hard size cap."""
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "video/*,application/octet-stream,*/*",
            })
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status} while downloading")
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise RuntimeError("Source video exceeds size cap")
                total = 0
                with destination.open("wb") as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > max_bytes:
                            raise RuntimeError("Download exceeded size cap")
                        output.write(block)
                if total < 100_000:
                    raise RuntimeError("Downloaded file is too small to be the expected video")
                return total
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            destination.unlink(missing_ok=True)
            if attempt < 2:
                print(f"Download retry {attempt+1}/2: {exc}", file=sys.stderr)
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Video download failed: {last}")


def probe(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type", "-of", "json", str(path),
    ], check=True, capture_output=True, text=True, timeout=90)
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration", 0))
    stream_types = {stream.get("codec_type") for stream in data.get("streams", [])}
    if not 600 <= duration <= 1200:
        raise ValueError(f"Expected 10–20-minute video, got {duration:.1f}s")
    if not {"video", "audio"} <= stream_types:
        raise ValueError("Expected both video and audio streams")
    return duration


def prepare(selected, root, local_only=False):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Install FFmpeg first: brew install ffmpeg")
    root = Path(root).resolve()
    videos_dir = root / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    result = make_manifest(selected)
    completed = []
    for key in selected:
        item = VIDEOS[key]
        destination = videos_dir / f"{item['id']}.mp4"
        if destination.is_file():
            print(f"Using existing verified video: {destination}", flush=True)
            duration = probe(destination)
            completed.append((key, duration))
            continue
        local_source = find_local_source(key, videos_dir)
        if local_source is None and local_only:
            expected = ", ".join(LOCAL_SOURCE_NAMES[key])
            raise ValueError(f"Local video source missing for {key}; expected {expected} in {videos_dir}")
        free_bytes = shutil.disk_usage(videos_dir).free
        if free_bytes < 1_500_000_000:
            raise RuntimeError("Need at least 1.5 GB free space to download/convert source media")
        with tempfile.TemporaryDirectory(prefix=".media-import-", dir=videos_dir) as temp:
            work = Path(temp)
            converted = work / "ready.mp4"
            if local_source is not None:
                source_file = local_source
                print(f"Using existing local download: {source_file}", flush=True)
            else:
                source_file = work / ("source.webm" if item["url"].endswith("webm") else "source.mp4")
                print(f"Downloading {item['title']} from {item['source_page']}", flush=True)
                download(item["url"], source_file)
            original_duration = probe(source_file)
            print(f"Encoding 480p H.264/AAC ({original_duration:.0f}s)", flush=True)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-i", str(source_file), "-map", "0:v:0", "-map", "0:a:0",
                "-vf", "fps=15,scale=854:480:force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                "-ac", "2", "-movflags", "+faststart", str(converted),
            ], check=True)
            actual_duration = probe(converted)
            if abs(actual_duration - original_duration) > 2:
                raise RuntimeError("Video conversion changed duration unexpectedly")
            os.replace(converted, destination)
        completed.append((key, actual_duration))
        print(f"Saved {destination} ({actual_duration:.0f}s)", flush=True)
    manifest = root / "portfolio-corpus.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != result:
            raise ValueError(f"Different manifest already exists: {manifest}; preserve annotations, select a fresh --root")
    else:
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return {"manifest": str(manifest),
            "videos": [{"id": VIDEOS[key]["id"], "duration_seconds": d}
                       for key, d in completed],
            "notice": "Attribution required; verify third-party rights before redistributing video."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=list(VIDEOS),
                        default=list(VIDEOS), help="Choose 1–3 sources; default all three")
    parser.add_argument("--root", default="data",
                        help="Local destination (ignored by git by default)")
    parser.add_argument("--plan", action="store_true", help="Print sources without downloading")
    parser.add_argument("--local-only", action="store_true",
                        help="Use existing local WebM/MP4 files; never download from the internet")
    args = parser.parse_args()
    try:
        if args.plan:
            report = {"selected": [{**VIDEOS[key]} for key in args.only],
                      "manifest_preview": make_manifest(args.only),
                      "note": "No media downloaded; CC BY attribution required"}
        else:
            report = prepare(args.only, args.root, local_only=args.local_only)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        parser.exit(2, f"Video preparation failed: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
