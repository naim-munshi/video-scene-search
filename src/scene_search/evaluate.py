import csv
import platform
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from .core import MODES, fuse, hybrid_fuse, metrics, read_json, sha256, validate_labels, write_json
from .statistics import paired_comparisons


def evaluate(engine, labels_path, output, split="test", k=5, *, plan_path=None,
             compare_equal_rrf=False):
    if split not in ("dev", "test") or k <= 0:
        raise ValueError("Invalid evaluation split or k")
    labels = read_json(labels_path)
    validate_labels(labels, engine.windows)
    if labels.get("build_sha256") != sha256(engine.root / "build.json"):
        raise ValueError("Labels belong to a different build; recheck annotations")
    if labels.get("annotation_protocol") or plan_path:
        if not plan_path:
            raise ValueError("Frozen-protocol labels require --plan")
        from .annotations import validate_plan
        plan = read_json(plan_path)
        validate_plan(labels, plan, engine.windows, sha256(engine.root / "build.json"))
        if labels.get("plan_sha256") != plan["plan_sha256"]:
            raise ValueError("Labels reference a different frozen plan")
    provenance = labels.get("label_provenance") or labels.get("annotation_method") or "not_recorded"
    weak_labels = (
        labels.get("human_verified") is False
        or labels.get("independent_ground_truth") is False
        or labels.get("evaluation_scope") == "weak_label_sanity_check_only_not_real_world_accuracy"
        or str(provenance).startswith("assistant_assisted")
    )
    if provenance == "synthetic_deterministic_not_manual":
        scope = "synthetic_fixture_only"
    elif labels.get("annotation_protocol") and provenance == "human_reviewed_self_reported":
        scope = "human_reviewed_self_reported"
    elif weak_labels:
        scope = "weak_label_sanity_check_only"
    else:
        scope = "unverified_annotations"
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
    if len(visual_batch) != len(queries) or len(transcript_batch) != len(queries):
        raise ValueError("Ranking batch length differs from query count")
    known_windows = {window["id"] for window in engine.windows}
    for q, visual, transcript in zip(queries, visual_batch, transcript_batch):
        for ranking in (visual, transcript):
            ids = [wid for wid, _ in ranking]
            if len(ids) != len(set(ids)) or not set(ids) <= known_windows:
                raise ValueError("Rankings contain duplicate or unknown window IDs")
        ranks = {"visual": visual, "transcript": transcript, "hybrid": hybrid_fuse(q["text"], visual, transcript)}
        if compare_equal_rrf:
            ranks["equal_rrf"] = fuse(visual, transcript)
        for mode, ranking in ranks.items():
            predicted = [wid for wid, _ in ranking[:k]]
            relevant = set(q["relevant"])
            values = metrics(predicted, relevant, k)
            details.append({"query_id": q["id"], "query": q["text"], "kind": q["kind"],
                "split": split, "mode": mode, **values, "predicted": predicted,
                "relevant": sorted(relevant), "max_possible_recall_at_k": min(k, len(relevant)) / len(relevant),
                "missed": sorted(relevant - set(predicted)),
                "false_positives": [p for p in predicted if p not in relevant],
                "amortized_all_modes_seconds_including_batch_model_load": elapsed})
    for mode in (*MODES, "equal_rrf") if compare_equal_rrf else MODES:
        for kind in ("all", "visual", "speech", "mixed"):
            group = [d for d in details if d["mode"] == mode and (kind == "all" or d["kind"] == kind)]
            if group:
                totals.append({"mode": mode, "kind": kind, "queries": len(group),
                    **{name: sum(d[name] for d in group) / len(group)
                       for name in (f"recall@{k}", f"hit@{k}", f"mrr@{k}")}})
    output.mkdir(parents=True)
    write_json(output / "per_query.json", details)
    comparison = paired_comparisons(details, k)
    write_json(output / "comparisons.json", comparison)
    write_json(output / "evidence.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "build_sha256": sha256(engine.root / "build.json"), "labels_sha256": sha256(labels_path),
        "label_provenance": provenance,
        "human_verified": labels.get("human_verified"),
        "independent_ground_truth": labels.get("independent_ground_truth"),
        "evaluation_scope": scope,
        "plan_sha256": labels.get("plan_sha256"),
        "equal_rrf_baseline": compare_equal_rrf,
        "implementation_sha256": {name: sha256(Path(__file__).with_name(name))
                                  for name in ("core.py", "evaluate.py", "statistics.py", "annotations.py")},
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
    if scope == "weak_label_sanity_check_only":
        lines += ["**AI-ASSISTED WEAK LABELS ONLY. Exploratory sanity check; "
                  "not independently human-verified real-world retrieval accuracy.**", ""]
    if labels.get("label_provenance") == "synthetic_deterministic_not_manual":
        lines += ["**SYNTHETIC BENCHMARK ONLY. Not a real-world quality claim.**", ""]
    if scope == "unverified_annotations":
        lines += ["**UNVERIFIED ANNOTATIONS. No verified human-review protocol was supplied.**", ""]
    if scope == "human_reviewed_self_reported":
        lines += ["**HUMAN REVIEW SELF-REPORTED. Frozen query/label checks passed; "
                  "software cannot certify reviewer independence or unseen test rankings.**", ""]
    lines += [
             "| Mode | Kind | Queries | Recall | Hit rate | MRR |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for t in totals:
        lines.append(f"| {t['mode']} | {t['kind']} | {t['queries']} | {t[f'recall@{k}']:.4f} | "
                     f"{t[f'hit@{k}']:.4f} | {t[f'mrr@{k}']:.4f} |")
    lines += ["", "## Paired comparison", "", comparison["limitations"], "",
              "Positive deltas favor heuristic hybrid; negative deltas favor the baseline.", "",
              "| Baseline | Metric | Mean delta | 95% bootstrap interval | Wins / ties / losses |",
              "| --- | --- | ---: | --- | --- |"]
    for row in comparison["comparisons"]:
        interval = row["percentile_95_interval"]
        bounds = f"[{interval[0]:.4f}, {interval[1]:.4f}]" if interval else "Insufficient queries"
        lines.append(f"| {row['baseline']} | {row['metric']} | {row['mean_delta']:.4f} | "
                     f"{bounds} | {row['wins']} / {row['ties']} / {row['losses']} |")
    oversized = [q for q in queries if len(q["relevant"]) > k]
    if oversized:
        lines += ["", "## Recall ceiling at k", "",
                  f"With exact-window Recall@{k}, a query with more than {k} labeled "
                  "windows cannot reach 100% regardless of model quality. "
                  f"Hit@{k} and MRR@{k} are also reported above.", ""]
        for q in oversized:
            ceiling = min(k, len(q["relevant"])) / len(q["relevant"])
            lines.append(
                f"- {q['id']}: {len(q['relevant'])} labeled windows; "
                f"maximum Recall@{k} = {ceiling:.4f}.")
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
