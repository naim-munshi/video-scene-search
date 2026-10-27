"""Audit the completed local engineering release and optional human playback sign-off.

Run from the repository root after the owner creates the existing reports:

    python scripts/final_acceptance.py

Optional:
    python scripts/final_acceptance.py \
      --browser-attestation ~/Downloads/browser-playback-self-attestation.json

This does NOT modify original media, indices, labels, reports or the repository.
Human reviewer-verified ground truth and secure public hosting remain unverified
or out of scope regardless of the browser checklist status.
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPECTED = {"portfolio_interview", "portfolio_film", "portfolio_nasa"}


def latest_report(pattern):
    candidates = sorted(
        (p for p in (REPO / "reports").glob(pattern) if p.is_file()),
        key=lambda p: (p.stat().st_mtime, p.name), reverse=True,
    )
    return candidates[0] if candidates else None


def latest_release():
    candidates = sorted(
        (p for p in (REPO / "reports").glob("portfolio-release-*")
         if p.is_dir() and (p / "RELEASE_STATUS.json").is_file()),
        key=lambda p: (p.stat().st_mtime, p.name), reverse=True,
    )
    return candidates[0] if candidates else None


def read_object(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def review_release(release_dir):
    root = Path(release_dir).expanduser().resolve()
    status = read_object(root / "RELEASE_STATUS.json")
    manifest = read_object(root / "input-manifest.json")
    audit = manifest.get("index_metadata_audit") or {}
    counts = manifest.get("query_counts") or {}
    required = (
        "dev/report.md", "dev/metrics.csv", "dev/per_query.json",
        "test/report.md", "test/metrics.csv", "test/per_query.json",
        "RELEASE_SUMMARY.md",
    )
    if not all((root / name).is_file() for name in required):
        raise ValueError("Release directory lacks required dev/test evidence")
    if status.get("status") != "LOCAL_ENGINEERING_CHECKS_PASS":
        raise ValueError("Local engineering release was not successful")
    if (counts != {"dev": 6, "test": 18}
            or status.get("development_queries") != 6
            or status.get("provisional_test_queries") != 18):
        raise ValueError("Unexpected development/test query counts")
    if (audit.get("status") != "metadata_integrity_passed"
            or audit.get("video_count") != 3
            or audit.get("window_count") != 252
            or audit.get("warnings") != []):
        raise ValueError("Three-video index integrity was not established")
    build = manifest.get("index_build_sha256")
    if not isinstance(build, str) or len(build) != 64:
        raise ValueError("Missing recorded index build SHA-256")
    if (audit.get("build_sha256") != build or
            manifest.get("independently_verified") is not False or
            status.get("accuracy_provenance") != "AI_ASSISTED_WEAK_LABELS_ONLY"):
        raise ValueError("Inconsistent or unsupported evaluation provenance")
    if "AI-ASSISTED WEAK LABELS" not in (
            root / "RELEASE_SUMMARY.md").read_text(encoding="utf-8"):
        raise ValueError("Release summary missing weak-label disclaimer")
    return {
        "status": "PASS",
        "build_sha256": build,
        "evidence_directory": str(root),
        "scope": "engineering_release_with_ai_assisted_weak_labels",
    }


def review_media(media_report):
    report = read_object(media_report)
    rows = report.get("sources")
    if (report.get("status") != "LOCAL_MEDIA_DECODE_PASS"
            or report.get("source_count") != 3
            or not isinstance(rows, list)
            or len(rows) != 3
            or {row.get("video_id") for row in rows} != EXPECTED
            or report.get("browser_playback_status") != "NOT_VERIFIED"):
        raise ValueError("The native media report does not cover the expected sources")
    for row in rows:
        times = row.get("decoded_frame_checkpoints_seconds")
        if (row.get("status") != "LOCAL_MEDIA_DECODE_PASS"
                or row.get("video_codec") != "h264"
                or row.get("audio_codec") != "aac"
                or not isinstance(times, list) or len(times) != 3
                or not all(isinstance(t, (float, int)) and t >= 0 for t in times)
                or row.get("audio_decoded_seconds", 0) < 1):
            raise ValueError(f"Missing required audio/video decoding evidence for {row.get('video_id')}")
    return {"status": "PASS", "media_report": str(Path(media_report).resolve()),
            "scope": "native_audio_and_video_spot_decode_not_browser_playback"}


def review_browser(attestation, build_sha256):
    if attestation is None:
        return {"status": "NOT_VERIFIED", "basis": "No operator playback attestation supplied"}
    report = read_object(attestation)
    if (report.get("status") != "USER_SELF_ATTESTED"
            or report.get("source") != "manual_Streamlit_checkbox_self_attestation"
            or report.get("not_automated_safari_test") is not True
            or report.get("build_sha256") != build_sha256
            or set(report.get("expected_sources", [])) != EXPECTED
            or report.get("confirmed_checkpoints") != 9
            or report.get("required_checkpoints") != 9
            or report.get("checkpoints_per_video") != ["Beginning", "Middle", "Near end"]
            or not isinstance(report.get("recorded_at_utc"), str)):
        raise ValueError("Browser self-attestation is incomplete or inconsistent")
    return {
        "status": "USER_SELF_ATTESTED",
        "basis": "Operator checked nine source/timestamp picture+sound observations",
        "independent_browser_certification": False,
    }


def evaluate_acceptance(release_dir=None, media_report=None, browser_attestation=None):
    root = release_dir or latest_release()
    native = media_report or latest_report("media-preflight-*.json")
    if root is None or native is None:
        raise ValueError("Required local release/media report missing; no final PASS can be claimed")
    engineering = review_release(root)
    media = review_media(native)
    browser = review_browser(browser_attestation, engineering["build_sha256"])
    return {
        "project": "Video Scene Search v0.1",
        "scope": "local_single_user_portfolio_prototype_only",
        "engineering": engineering,
        "native_media_decoding": media,
        "browser_picture_sound": browser,
        "independent_ground_truth": "NOT_VERIFIED",
        "production_hosting_security": "OUT_OF_SCOPE",
        "overall": (
            "LOCAL_PORTFOLIO_OPERATOR_SELF_ATTESTED"
            if browser["status"] == "USER_SELF_ATTESTED"
            else "LOCAL_ENGINEERING_PASS_BROWSER_PENDING"
        ),
        "note": "Neither result establishes independently verified retrieval accuracy or public production security.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--media-report", type=Path)
    parser.add_argument("--browser-attestation", type=Path)
    parser.add_argument("--output", type=Path, help="Optional NEW JSON report; never overwrite")
    args = parser.parse_args()
    try:
        result = evaluate_acceptance(
            args.release_dir, args.media_report, args.browser_attestation)
        if args.output:
            path = args.output.expanduser()
            if path.exists():
                raise ValueError(f"Output already exists: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
                f.write("\n")
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Final acceptance check BLOCKED: {exc}\n")


if __name__ == "__main__":
    main()
