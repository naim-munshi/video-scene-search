"""Persistent local review sessions; never loads a model or shows ranked results."""
import copy
import time
import uuid
from pathlib import Path

from .annotations import freeze_labels, init_labels, finalize_labels, query_spec, write_new
from .core import read_json, sha256, validate_labels


def load_corpus(index):
    root = Path(index).expanduser().resolve()
    build = read_json(root / "build.json")
    # Metadata only: no untrusted native index deserialization or model imports.
    if build.get("schema_version") != 1:
        raise ValueError("Unsupported index schema")
    for name in ("corpus.json", "windows.json"):
        expected = build.get("files", {}).get(name)
        if not expected or sha256(root / name) != expected:
            raise ValueError(f"Index metadata integrity failed: {name}")
    videos = read_json(root / "corpus.json")["videos"]
    windows = read_json(root / "windows.json")
    if not videos or not windows:
        raise ValueError("Index must contain videos and windows")
    ids = {v["id"] for v in videos}
    if len(ids) != len(videos) or len({w["id"] for w in windows}) != len(windows):
        raise ValueError("Duplicate video or window IDs")
    if any(w["video_id"] not in ids for w in windows):
        raise ValueError("Window references an unknown source")
    return {"root": root, "build_sha256": sha256(root / "build.json"),
            "videos": videos, "windows": windows}


def new_session(index, directory, count=48, dev_count=12):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    try:
        init_labels(index, directory / "draft.json", count, dev_count)
    except Exception:
        # Never delete a directory containing someone else's work.
        if not any(directory.iterdir()):
            directory.rmdir()
        raise
    return directory


def latest_labels(session):
    session = Path(session)
    snapshots = sorted(session.glob("review-*.json"))
    return snapshots[-1] if snapshots else session / "draft.json"


def save_snapshot(session, labels):
    path = Path(session) / f"review-{time.time_ns():020d}-{uuid.uuid4().hex[:8]}.json"
    write_new(path, labels)
    return path


def save_queries(session, rows):
    session = Path(session)
    if (session / "plan.json").exists():
        raise ValueError("Queries are frozen; start a new session to change them")
    labels = read_json(latest_labels(session))
    if len(rows) != len(labels["queries"]) or any(
            a.get("id") != b["id"] for a, b in zip(rows, labels["queries"])):
        raise ValueError("Keep the original query IDs and row order")
    # Saving unfinished text is allowed; freeze performs full validation.
    for q, row in zip(labels["queries"], rows):
        if any(not isinstance(row.get(k), str) for k in ("text", "kind", "split")):
            raise ValueError("Query text, kind and split must be strings")
        q.update({k: row[k] for k in ("text", "kind", "split")})
    return save_snapshot(session, labels)


def freeze_session(index, session):
    session = Path(session)
    return freeze_labels(index, latest_labels(session), session / "plan.json")


def save_review(index, session, query_id, relevant, reviewer, note, reviewed):
    session = Path(session)
    if (session / "reviewed.json").exists():
        raise ValueError("Session is finalized; preserve it and create a new study for changes")
    corpus = load_corpus(index)
    labels = read_json(latest_labels(session))
    plan = read_json(session / "plan.json")
    from .annotations import digest
    if plan.get("plan_sha256") != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise ValueError("Frozen plan hash mismatch")
    if labels["build_sha256"] != corpus["build_sha256"] or plan["build_sha256"] != corpus["build_sha256"]:
        raise ValueError("Review session belongs to a different index")
    if query_spec(labels["queries"]) != plan["queries"]:
        raise ValueError("Frozen query fields changed")
    q = next((q for q in labels["queries"] if q["id"] == query_id), None)
    if q is None:
        raise ValueError("Unknown query ID")
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(note, str) or not note.strip():
        raise ValueError("Reviewer alias and evidence note are required")
    if reviewed is not True:
        raise ValueError("Confirm that you watched the source and checked all relevant windows")
    updated = {**copy.deepcopy(q), "relevant": list(relevant),
               "review": {"reviewed": True, "reviewer": reviewer.strip(), "evidence_note": note.strip()}}
    validate_labels({"status": "annotated", "queries": [updated]}, corpus["windows"])
    labels["queries"] = [updated if x["id"] == query_id else x for x in labels["queries"]]
    return save_snapshot(session, labels)


def finalize_session(index, session):
    session = Path(session)
    return finalize_labels(index, latest_labels(session), session / "plan.json", session / "reviewed.json")
