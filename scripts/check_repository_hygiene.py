"""Fail CI if generated or private media/model artifacts enter the Git index.

The check reviews Git-tracked path names only; it does not inspect private
local files or upload media. Run: python scripts/check_repository_hygiene.py
"""
import subprocess
import sys
from pathlib import PurePosixPath

PRIVATE_DIRS = {"data", "artifacts", "evaluation", "reports"}
PRIVATE_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".wav",
    ".faiss", ".safetensors", ".ckpt", ".pth", ".pt",
    ".pem", ".key",
}


def forbidden_tracked_paths(paths):
    blocked = []
    for value in paths:
        path = str(value).replace("\\", "/")
        parts = PurePosixPath(path).parts
        if not parts:
            continue
        filename = parts[-1]
        suffix = PurePosixPath(path).suffix.lower()
        if (
            any(part in PRIVATE_DIRS for part in parts[:-1])
            or filename == ".env"
            or (filename.startswith(".env.") and filename != ".env.example")
            or suffix in PRIVATE_EXTENSIONS
            or filename == ".DS_Store"
        ):
            blocked.append(path)
    return sorted(set(blocked))


def main():
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    paths = [
        value.decode("utf-8", "surrogateescape")
        for value in result.stdout.split(b"\0") if value
    ]
    blocked = forbidden_tracked_paths(paths)
    if blocked:
        print(
            "FAIL: local/private media or secret-like files are tracked:",
            file=sys.stderr,
        )
        for path in blocked:
            print(" - " + path, file=sys.stderr)
        print("Remove these files from Git tracking before release.", file=sys.stderr)
        return 1
    print(f"Repository hygiene: PASS ({len(paths)} tracked paths checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
