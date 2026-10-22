"""Pure retrieval and evaluation logic; no ML downloads required."""
import hashlib
import json
import math
from pathlib import Path

MODES = ("visual", "transcript", "hybrid")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def make_windows(video_id, duration, seconds=10):
    if not math.isfinite(duration) or duration <= 0 or seconds <= 0:
        raise ValueError("Duration and window size must be positive")
    return [{"id": f"{video_id}:{i:05d}", "video_id": video_id,
             "start": i * seconds, "end": min((i + 1) * seconds, duration)}
            for i in range(math.ceil(duration / seconds))]


def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def aggregate_rank(scores, indices, rows):
    """Max cosine score per distinct window, deterministic ties."""
    best = {}
    for score, idx in zip(scores, indices):
        if idx < 0:
            continue
        for window_id in rows[int(idx)]["window_ids"]:
            best[window_id] = max(best.get(window_id, -math.inf), float(score))
    return sorted(best.items(), key=lambda x: (-x[1], x[0]))


def fuse(visual, transcript, rank_constant=60):
    if rank_constant <= 0:
        raise ValueError("RRF constant must be positive")
    scores = {}
    for ranking in (visual, transcript):
        seen = set()
        for rank, (wid, _) in enumerate(ranking, 1):
            if wid not in seen:
                scores[wid] = scores.get(wid, 0) + 1 / (rank_constant + rank)
                seen.add(wid)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def metrics(predicted, relevant, k=5):
    if k <= 0 or not relevant:
        raise ValueError("Positive k and at least one relevant window are required")
    relevant = set(relevant)
    top = list(dict.fromkeys(predicted))[:k]
    hits = len(set(top) & relevant)
    rr = next((1 / i for i, wid in enumerate(top, 1) if wid in relevant), 0.0)
    return {f"recall@{k}": hits / len(relevant), f"hit@{k}": float(hits > 0),
            f"mrr@{k}": rr}


def validate_labels(labels, windows):
    if labels.get("status") != "annotated":
        raise ValueError("Labels are a draft. Review them, then set status to annotated.")
    queries = labels.get("queries", [])
    if not queries:
        raise ValueError("No evaluation queries")
    known = {w["id"] for w in windows}
    seen, texts = set(), set()
    for q in queries:
        if not q.get("id") or q["id"] in seen:
            raise ValueError("Query IDs must be nonempty and unique")
        seen.add(q["id"])
        text = q.get("text", "").strip().casefold()
        if not text or text in texts:
            raise ValueError("Query text must be nonempty and unique across splits")
        texts.add(text)
        if q.get("split") not in ("dev", "test"):
            raise ValueError("Every query needs a dev or test split")
        if q.get("kind") not in ("visual", "speech", "mixed"):
            raise ValueError("Query kind must be visual, speech or mixed")
        relevant = q.get("relevant", [])
        if not relevant or len(relevant) != len(set(relevant)) or not set(relevant) <= known:
            raise ValueError(f"Invalid or missing relevant window IDs for {q['id']}")
