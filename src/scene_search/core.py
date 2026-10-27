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
        if not 0 <= int(idx) < len(rows):
            continue
        for window_id in rows[int(idx)]["window_ids"]:
            best[window_id] = max(best.get(window_id, -math.inf), float(score))
    return sorted(best.items(), key=lambda x: (-x[1], x[0]))


def fuse(visual, transcript, rank_constant=60, visual_weight=1.0,
         transcript_weight=1.0):
    """Weighted reciprocal rank fusion, without comparing modality cosine scores.

    Existing two-argument calls retain equal-weight RRF. Weights are applied
    only to ranking contributions; a missing modality never suppresses the other.
    """
    if not math.isfinite(rank_constant) or rank_constant <= 0:
        raise ValueError("RRF constant must be positive")
    weights = (visual_weight, transcript_weight)
    if any(not math.isfinite(w) or w < 0 for w in weights) or not any(weights):
        raise ValueError("Fusion weights must be finite, nonnegative and nonzero")
    scores = {}
    for ranking, weight in zip((visual, transcript), weights):
        if weight == 0:
            continue
        seen = set()
        for rank, (wid, _) in enumerate(ranking, 1):
            if wid not in seen:
                scores[wid] = scores.get(wid, 0.0) + weight / (rank_constant + rank)
                seen.add(wid)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def hybrid_weights(query):
    """Transparent query-intent routing; a heuristic, not an accuracy claim.

    Visual cues and spoken-content cues may co-occur. For a scene description
    with no recognized visual cue, prioritize transcript evidence but retain
    visual candidates. Speech-free corpora still use visual ranking alone.
    """
    import re
    if not isinstance(query, str):
        raise ValueError("Query must be a string")
    q = query.casefold()
    spoken = bool(re.search(
        r"\b(says?|said|speaks?|speaking|spoken|talks?|talking|narrat(?:or|ion|es|es?)|"
        r"voice|audio|speech|transcript|mentions?|discuss(?:es|ed|ing)?|"
        r"explain(?:s|ed|ing)?|announc(?:es|ed|ing)|heard|hearing|quote|"
        r"conversation|dialogue)\b", q))
    visible = bool(re.search(
        r"\b(visual|scene|screen|frame|shown?|showing|appears?|visible|"
        r"colors?|colours?|red|blue|green|yellow|purple|orange|black|"
        r"white|pink|wears?|wearing|standing|walking|sitting|people|"
        r"person|woman|man|men|women|child|animal|car|train|building|table|laptop|"
        r"seated|seating|faces?|close-up|shot|camera|captions?|subtitles?|"
        r"gestures?|hands?|railing|rover|rocket|robots?|machinery|machine|"
        r"holographic|equipment|laboratory|astronaut|futuristic|outdoors?)\b", q))
    if spoken and not visible:
        return 0.2, 1.0
    if visible and not spoken:
        return 1.0, 0.35
    if not spoken and not visible:
        return 0.35, 1.0
    return 1.0, 1.0


def hybrid_fuse(query, visual, transcript, rank_constant=60):
    if not transcript:
        return fuse(visual, [], rank_constant=rank_constant)
    if not visual:
        return fuse([], transcript, rank_constant=rank_constant)
    visual_weight, transcript_weight = hybrid_weights(query)
    return fuse(visual, transcript, rank_constant=rank_constant,
                visual_weight=visual_weight, transcript_weight=transcript_weight)


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
