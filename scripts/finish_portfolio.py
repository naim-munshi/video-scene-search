"""Non-destructive local portfolio release audit and provisional benchmark.

Run from the repository with cached models:
python scripts/finish_portfolio.py --device mps

Writes a NEW reports/portfolio-release-YYYYMMDD-HHMMSS directory. Never edits
source videos, FAISS indexes, labels or existing reports. AI-assisted results
are always labeled provisional, not independent retrieval accuracy.
"""
import argparse
import json
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
from scene_search.core import read_json, sha256, validate_labels, write_json

SOURCES = (
    "src/scene_search/core.py",
    "src/scene_search/search.py",
    "src/scene_search/evaluate.py",
    "src/scene_search/query_worker.py",
)
EXPECTED_VIDEOS = {"portfolio_nasa", "portfolio_interview", "portfolio_film"}


def inspect_release_inputs(index, labels):
    from scripts.acceptance_check import audit_index
    index = Path(index).expanduser().resolve()
    labels = Path(labels).expanduser().resolve()
    audit = audit_index(index)
    data = read_json(labels)
    validate_labels(data, read_json(index / "windows.json"))
    if data.get("build_sha256") != sha256(index / "build.json"):
        raise ValueError("Labels belong to another index build")
    queries = data["queries"]
    if len(queries) != 24 or sum(q["split"] == "dev" for q in queries) != 6 or sum(q["split"] == "test" for q in queries) != 18:
        raise ValueError("Expected exactly 24 queries: 6 dev and 18 test")
    ids = {v["id"] for v in read_json(index / "corpus.json")["videos"]}
    if ids != EXPECTED_VIDEOS:
        raise ValueError("Expected the original three-video portfolio corpus")
    origin = data.get("label_provenance") or data.get("annotation_method") or "not_recorded"
    weak = (data.get("human_verified") is False
            or data.get("independent_ground_truth") is False
            or data.get("evaluation_scope") == "weak_label_sanity_check_only_not_real_world_accuracy"
            or str(origin).startswith("assistant_assisted"))
    verified = (not weak and data.get("human_verified") is True
                and data.get("independent_ground_truth") is True)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_build_sha256": sha256(index / "build.json"),
        "labels_sha256": sha256(labels),
        "code_sha256": {p: sha256(REPO / p) for p in SOURCES},
        "label_provenance": origin,
        "independently_verified": verified,
        "assistant_assisted_weak_labels": weak,
        "query_counts": {"dev": 6, "test": 18},
        "index_metadata_audit": audit,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def summary_table(rows, split):
    result = ["### " + split + " (macro across queries)", "",
              "| Mode | Recall@5 | Hit@5 | MRR@5 |",
              "| --- | ---: | ---: | ---: |"]
    for name in ("visual", "transcript", "hybrid"):
        row = next(r for r in rows if r["mode"] == name and r["kind"] == "all")
        result.append("| {} | {:.4f} | {:.4f} | {:.4f} |".format(
            name, row["recall@5"], row["hit@5"], row["mrr@5"]))
    return result


def make_summary(inputs, dev, test):
    lines = [
        "# Video Scene Search — local release evidence", "",
        "**Retrieval:** Whisper ASR, CLIP, multilingual MiniLM, FAISS, "
        "intent-weighted RRF; three licensed-source videos, 10-second windows.", "",
        "**LABEL WARNING: AI-assisted weak-label scores are exploratory "
        "sanity checks, NOT independently human-verified real-world accuracy.**"
        if not inputs["independently_verified"] else
        "**Ground-truth verification was asserted by file metadata; this "
        "script cannot independently attest that it happened.**", "",
        "Build SHA-256: " + inputs["index_build_sha256"], "",
        "Labels SHA-256: " + inputs["labels_sha256"], "",
    ]
    lines += summary_table(dev, "Development (6 queries)") + [""]
    lines += summary_table(test, "Provisional test (18 queries)") + [""]
    lines += [
        "## Acceptance matrix", "",
        "| Gate | Status |", "| --- | --- |",
        "| Three-video index metadata SHA-256 and references | PASS |",
        "| Development and test model retrieval execution | PASS |",
        "| Full browser playback and UI on Mac/Safari | NOT VERIFIED IN THIS RUN |",
        "| Human-independent completeness of 24 relevance labels | NOT VERIFIED IN THIS RUN |",
        "| Production multi-tenant security | OUT OF SCOPE: local-only prototype |",
        "", "## Interpretation and next actions", "",
        "Recall@5 has a ceiling if there are more than five relevant windows "
        "for a query. Read dev/report.md and test/report.md for per-query failures.",
        "This small-corpus benchmark is an engineering smoke, not generalization "
        "evidence. Check three source videos in Safari for playable timestamps.",
        "To claim independently measured performance on a CV, have another "
        "reviewer check the ground truth from actual footage/audio. "
        "Record a short attributed local demo.",
        "", "## CV-ready implementation statement (without unverified scores)", "",
        "Built a local timestamped multimodal video search proof of concept using "
        "faster-whisper, CLIP, MiniLM, FAISS, Streamlit and weighted reciprocal "
        "rank fusion; instrumented 24-query exploratory evaluation.", "",
    ]
    return "\n".join(lines)


def package_reports(root):
    archive = root / "shareable-release-evidence.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and p != archive and p.suffix in {".json", ".csv", ".md"}:
                zf.write(p, p.relative_to(root))
    return archive


def finish(index, labels, output, device="mps", offline=True):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Release output already exists; choose a new folder")
    inputs = inspect_release_inputs(index, labels)
    output.mkdir(parents=True)
    write_json(output / "input-manifest.json", inputs)
    if offline:
        from scene_search.query_worker import enable_offline_cache
        enable_offline_cache()
    try:
        from scene_search.search import SearchEngine
        from scene_search.evaluate import evaluate
        engine = SearchEngine(index, device=device)
        dev = evaluate(engine, labels, output / "dev", "dev", 5)
        test = evaluate(engine, labels, output / "test", "test", 5)
        (output / "RELEASE_SUMMARY.md").write_text(
            make_summary(inputs, dev, test), encoding="utf-8")
        result = {
            "status": "LOCAL_ENGINEERING_CHECKS_PASS",
            "accuracy_provenance": ("asserted_verified" if inputs["independently_verified"]
                                    else "AI_ASSISTED_WEAK_LABELS_ONLY"),
            "source_videos": 3,
            "development_queries": 6,
            "provisional_test_queries": 18,
            "browser_acceptance": "NOT_VERIFIED",
            "production_security": "OUT_OF_SCOPE",
            "summary": str(output / "RELEASE_SUMMARY.md"),
        }
        write_json(output / "RELEASE_STATUS.json", result)
        result["evidence_zip"] = str(package_reports(output))
        return result
    except Exception as exc:
        write_json(output / "RELEASE_STATUS.json",
                   {"status": "INCOMPLETE", "error": str(exc),
                    "note": "Existing media/index/labels were not changed"})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/portfolio-real-v2")
    parser.add_argument("--labels", default="evaluation/portfolio-real-v2-weak-labels.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"),
                        default="mps")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.preflight_only:
            print(json.dumps(inspect_release_inputs(args.index, args.labels), indent=2))
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = args.output or str(REPO / "reports" / ("portfolio-release-" + stamp))
        result = finish(args.index, args.labels, target, args.device,
                        offline=not args.allow_network)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, ImportError) as exc:
        parser.exit(2, f"Portfolio completion check failed: {exc}\n")


if __name__ == "__main__":
    main()
