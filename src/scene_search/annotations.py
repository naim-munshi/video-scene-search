"""Local annotation protocol. Records human declarations, never certifies them."""
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .core import read_json, sha256, validate_labels

PROTOCOL = "frozen_queries_v1"
QUERY_FIELDS = ("id", "text", "kind", "split")


def normalized_text(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents accidental replacement through symlinks.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def query_spec(queries):
    if not isinstance(queries, list) or not queries:
        raise ValueError("Queries must be a nonempty list")
    result, ids, texts = [], set(), set()
    for q in queries:
        if not isinstance(q, dict):
            raise ValueError("Each query must be an object")
        if any(not isinstance(q.get(key), str) for key in QUERY_FIELDS):
            raise ValueError("Each query needs string id, text, kind and split")
        text = normalized_text(q["text"])
        if not q["id"].strip() or q["id"] in ids or not text or text in texts:
            raise ValueError("Query IDs and normalized texts must be nonempty and unique")
        if len(q["text"]) > 500 or q["kind"] not in ("visual", "speech", "mixed"):
            raise ValueError("Invalid query kind or text longer than 500 characters")
        if q["split"] not in ("dev", "test"):
            raise ValueError("Query split must be dev or test")
        ids.add(q["id"])
        texts.add(text)
        result.append({key: q[key] for key in QUERY_FIELDS})
    if {q["split"] for q in result} != {"dev", "test"}:
        raise ValueError("Include both dev and test queries before freezing")
    return result


def init_labels(index, output, count=48, dev_count=12):
    if not 2 <= count <= 128 or not 1 <= dev_count < count:
        raise ValueError("Use 2–128 queries and 1 <= dev-count < count")
    root = Path(index)
    windows = read_json(root / "windows.json")
    if not windows:
        raise ValueError("Index has no windows")
    labels = {"status": "draft", "build_sha256": sha256(root / "build.json"),
              "label_provenance": "unreviewed", "queries": [
                  {"id": f"q{i+1:02d}", "text": "",
                   "kind": ("visual", "speech", "mixed")[i % 3],
                   "split": "dev" if i < dev_count else "test", "relevant": [],
                   "review": {"reviewed": False, "reviewer": "", "evidence_note": ""}}
                  for i in range(count)]}
    write_new(output, labels)
    return {"labels": str(output), "queries": count, "dev": dev_count,
            "test": count - dev_count, "next": "Write fresh queries, then freeze-labels before ranking or labeling"}


def freeze_labels(index, labels_path, output, exclude_labels=()):
    root, labels = Path(index), read_json(labels_path)
    queries = query_spec(labels.get("queries"))
    if labels.get("status") != "draft" or any(q.get("relevant") for q in labels["queries"]):
        raise ValueError("Freeze a draft before adding relevant IDs or inspecting rankings")
    build_hash = sha256(root / "build.json")
    if labels.get("build_sha256") != build_hash:
        raise ValueError("Labels belong to a different build")
    exclusions, excluded_texts = [], set()
    for path in exclude_labels:
        previous = read_json(path)
        excluded_texts.update(normalized_text(q["text"]) for q in previous["queries"])
        exclusions.append(sha256(path))
    if any(normalized_text(q["text"]) in excluded_texts for q in queries):
        raise ValueError("A query reuses an excluded development/previous-test query")
    payload = {"protocol": PROTOCOL, "build_sha256": build_hash,
               "queries": queries, "excluded_label_sha256": exclusions,
               "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "matching": "exact fixed-window IDs; answerable queries only",
               "note": "Local audit record; not proof that rankings were unseen"}
    plan = {**payload, "plan_sha256": digest(payload)}
    write_new(output, plan)
    return {"plan": str(output), "plan_sha256": plan["plan_sha256"],
            "next": "Watch source media without search rankings; fill relevant IDs and each review record"}


def validate_plan(labels, plan, windows, build_hash):
    payload = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if plan.get("protocol") != PROTOCOL or plan.get("plan_sha256") != digest(payload):
        raise ValueError("Invalid frozen plan or plan hash")
    if plan["build_sha256"] != build_hash or labels.get("build_sha256") != build_hash:
        raise ValueError("Plan/labels belong to a different build")
    if query_spec(labels["queries"]) != plan["queries"]:
        raise ValueError("Query text, IDs, kinds or splits changed after freeze")
    validate_labels({**labels, "status": "annotated"}, windows)
    for q in labels["queries"]:
        review = q.get("review", {})
        if not isinstance(review, dict) or review.get("reviewed") is not True:
            raise ValueError(f"Human review missing for {q['id']}")
        for field in ("reviewer", "evidence_note"):
            if not isinstance(review.get(field), str) or not review[field].strip():
                raise ValueError(f"Review {field} missing for {q['id']}")


def finalize_labels(index, labels_path, plan_path, output):
    root = Path(index)
    labels, plan = read_json(labels_path), read_json(plan_path)
    validate_plan(labels, plan, read_json(root / "windows.json"), sha256(root / "build.json"))
    result = {**labels, "status": "annotated", "annotation_protocol": PROTOCOL,
              "plan_sha256": plan["plan_sha256"],
              "label_provenance": "human_reviewed_self_reported",
              "human_verified": True, "independent_ground_truth": None,
              "evaluation_scope": "human_reviewed_self_reported",
              "finalized_at_utc": datetime.now(timezone.utc).isoformat()}
    write_new(output, result)
    return {"labels": str(output), "scope": "Human review is self-reported, not independently certified"}
