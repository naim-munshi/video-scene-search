import csv
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .core import MODES, hybrid_fuse, metrics, read_json, sha256, validate_labels, write_json


def evaluate(engine, labels_path, output, split="test", k=5):
    if split not in ("dev", "test") or k <= 0:
        raise ValueError("Invalid evaluation split or k")
    labels = read_json(labels_path)
    validate_labels(labels, engine.windows)
    if labels.get("build_sha256") != sha256(engine.root / "build.json"):
        raise ValueError("Labels belong to a different build; recheck annotations")
    provenance = labels.get("label_provenance") or labels.get("annotation_method") or "not_recorded"
    weak_labels = (
        labels.get("human_verified") is False
        or labels.get("independent_ground_truth") is False
        or labels.get("evaluation_scope") == "weak_label_sanity_check_only_not_real_world_accuracy"
        or str(provenance).startswith("assistant_assisted")
    )
    queries = [q for q in labels["queries"] if q["split"] == split]
    if not queries:
        raise ValueError(f"No queries in split {split}")
    output = Path(output)
    if output.exists():
        raise ValueError("Report directory exists; choose a new output")
    details, totals = [], []
    started = perf_counter()
    texts = [q["text"] for q in queries]
    if callable(getattr(engine, "rankings_batch", None)):
        visual_batch = engine.rankings_batch(texts, "visual")
        transcript_batch = engine.rankings_batch(texts, "transcript")
    else:
        visual_batch = [engine.rankings(text, "visual") for text in texts]
        transcript_batch = [engine.rankings(text, "transcript") for text in texts]
    elapsed = (perf_counter() - started) / len(queries)  # amortized per query
    for q, visual, transcript in zip(queries, visual_batch, transcript_batch):
        ranks = {"visual": visual, "transcript": transcript, "hybrid": hybrid_fuse(q["text"], visual, transcript)}
        for mode, ranking in ranks.items():
            predicted = [wid for wid, _ in ranking[:k]]
            relevant = set(q["relevant"])
            values = metrics(predicted, relevant, k)
            details.append({"query_id": q["id"], "query": q["text"], "kind": q["kind"],
                "split": split, "mode": mode, **values, "predicted": predicted,
                "relevant": sorted(relevant), "missed": sorted(relevant - set(predicted)),
                "false_positives": [p for p in predicted if p not in relevant],
                "amortized_all_modes_seconds_including_batch_model_load": elapsed})
    for mode in MODES:
        for kind in ("all", "visual", "speech", "mixed"):
            group = [d for d in details if d["mode"] == mode and (kind == "all" or d["kind"] == kind)]
            if group:
                totals.append({"mode": mode, "kind": kind, "queries": len(group),
                    **{name: sum(d[name] for d in group) / len(group)
                       for name in (f"recall@{k}", f"hit@{k}", f"mrr@{k}")}})
    output.mkdir(parents=True)
    write_json(output / "per_query.json", details)
    write_json(output / "evidence.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "build_sha256": sha256(engine.root / "build.json"), "labels_sha256": sha256(labels_path),
        "label_provenance": provenance,
        "human_verified": labels.get("human_verified"),
        "independent_ground_truth": labels.get("independent_ground_truth"),
        "evaluation_scope": "weak_label_sanity_check_only" if weak_labels else "provided_annotations",
        "split": split, "k": k, "query_count": len(queries), "python": platform.python_version(),
        "platform": platform.platform(), "matching": ("Exact deterministic synthetic fixed-window IDs"
                     if labels.get("label_provenance") == "synthetic_deterministic_not_manual"
                     else "Exact provided fixed-window IDs"),
        "aggregation": "Macro mean across queries", "rrf_constant": 60,
        "latency_note": "Reported per-query runtime amortizes model startup over each evaluation batch",
        "fusion_policy": "Heuristic query-intent weighted RRF; inspect hybrid_weights",
        "candidate_policy": "All indexed rows, max cosine per window, intent-weighted full-rank RRF"})
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(totals[0]))
        writer.writeheader()
        writer.writerows(totals)
    lines = ["# Retrieval evaluation", "", f"Split: {split}; queries: {len(queries)}; k: {k}.", "",
             f"Label provenance: {provenance}.", ""]
    if weak_labels:
        lines += ["**AI-ASSISTED WEAK LABELS ONLY. Exploratory sanity check; "
                  "not independently human-verified real-world retrieval accuracy.**", ""]
    if labels.get("label_provenance") == "synthetic_deterministic_not_manual":
        lines += ["**SYNTHETIC BENCHMARK ONLY. Not a real-world quality claim.**", ""]
    lines += [
             "| Mode | Kind | Queries | Recall | Hit rate | MRR |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for t in totals:
        lines.append(f"| {t['mode']} | {t['kind']} | {t['queries']} | {t[f'recall@{k}']:.4f} | "
                     f"{t[f'hit@{k}']:.4f} | {t[f'mrr@{k}']:.4f} |")
    lines += ["", "## Failure review", "",
              "These are retrieval mismatches, not automatically diagnosed causes. Review the video.", ""]
    for d in details:
        if d["missed"] or d["false_positives"]:
            lines += [f"### {d['query_id']} / {d['mode']}", "",
                      f"Query: {d['query']}", f"Missed: {', '.join(d['missed']) or 'none'}",
                      f"False positives: {', '.join(d['false_positives']) or 'none'}",
                      "Human diagnosis: TODO (ASR / sparse sampling / visual ambiguity / labels / fusion).", ""]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return totals
