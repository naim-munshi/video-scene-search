"""Install the reviewed, owner-supplied Video Scene Search demo screenshot ZIP.

Usage:
    python scripts/install_demo_gallery.py ~/Downloads/video_scene_search_demo_gallery.zip

The exact archive and image SHA-256 fingerprints are checked BEFORE any file is
written. Only the gallery Markdown, three JPEGs and provenance manifest are
allowed. Existing files are never overwritten if their contents differ.
This script does not download anything, run ML models, commit or push to GitHub.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED_ARCHIVE_SHA256 = "1b153fdbf0fe4d352dfd5017e70cc86151325073a005b229ce136099992ee2ec"
EXPECTED_IMAGES = {
    "docs/assets/demo/01-overview.jpg":
        "06ad310a1a0213f40398c6cdfb584769d71dffd44e71ee7684358c034c36e670",
    "docs/assets/demo/02-video-library.jpg":
        "d771d2e7e97668a521d2aa4aa1be274bc90e99263eb6ff5a840d4a8ff5a6f099",
    "docs/assets/demo/03-timestamp-search.jpg":
        "c0bfaa4be0dc7a6087ffbccadc668a5be6119f6f0447cdd6233ceee209d9a4e1",
}
TEXT_FILES = ("docs/DEMO_GALLERY.md", "docs/assets/demo/manifest.json")
ALLOWED = set(EXPECTED_IMAGES) | set(TEXT_FILES) | {"DEMO_ASSETS_README.txt"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit_bundle(archive):
    archive = Path(archive).expanduser()
    if not archive.is_file():
        raise FileNotFoundError(
            f"ZIP not found: {archive}. Download the gallery ZIP from the "
            "ChatGPT link first, then locate it in Downloads.")
    if digest(archive.read_bytes()) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("Wrong or changed demo ZIP: SHA-256 mismatch")
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if len(names) != len(set(names)) or set(names) != ALLOWED:
            raise ValueError("Unexpected or missing entries in demo ZIP")
        contents = {}
        for name in names:
            info = zf.getinfo(name)
            if info.is_dir() or info.file_size > 500_000:
                raise ValueError("Invalid gallery archive entry")
            contents[name] = zf.read(name)
    for name, sha in EXPECTED_IMAGES.items():
        if digest(contents[name]) != sha:
            raise ValueError(f"Image checksum mismatch: {name}")
        if not contents[name].startswith(b"\xff\xd8\xff"):
            raise ValueError(f"Not a JPEG image: {name}")
    manifest = json.loads(contents["docs/assets/demo/manifest.json"])
    declared = {row["file"]: row["sha256"] for row in manifest["files"]}
    if declared != EXPECTED_IMAGES:
        raise ValueError("Gallery provenance manifest does not match images")
    text = contents["docs/DEMO_GALLERY.md"].decode("utf-8")
    for image_name in EXPECTED_IMAGES:
        if Path(image_name).name not in text:
            raise ValueError("Gallery Markdown does not reference all images")
    return contents


def install(archive, destination=REPO):
    contents = audit_bundle(archive)
    base = Path(destination).expanduser().resolve()
    if not (base / ".git").exists():
        raise ValueError(f"Not a Git repository root: {base}")
    targets = {}
    for name in set(EXPECTED_IMAGES) | set(TEXT_FILES):
        output = (base / name).resolve()
        if not output.is_relative_to(base):
            raise ValueError("Unsafe output path")
        if output.exists() and output.read_bytes() != contents[name]:
            raise FileExistsError(f"Refusing to overwrite changed file: {output}")
        targets[output] = contents[name]
    for output, data in targets.items():
        if not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as f:
                f.write(data)
    return sorted(p.relative_to(base).as_posix() for p in targets)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Downloaded demo ZIP path")
    parser.add_argument("--root", type=Path, default=REPO)
    args = parser.parse_args()
    try:
        result = install(args.archive, args.root)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.exit(2, f"Demo installation blocked: {exc}\n")
    print("Verified real UI screenshots installed safely:")
    for path in result:
        print(f"  {path}")
    print("Next: git add docs/DEMO_GALLERY.md docs/assets/demo && git commit && git push")


if __name__ == "__main__":
    main()
