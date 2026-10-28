"""Seeded paired query bootstrap; uncertainty conditional on the supplied labels."""
import random


def paired_comparisons(details, k, samples=2000, seed=42):
    by_mode = {}
    for row in details:
        by_mode.setdefault(row["mode"], {})[row["query_id"]] = row
    candidate = by_mode["hybrid"]
    query_ids = sorted(candidate)
    rng = random.Random(seed)
    draws = [[rng.randrange(len(query_ids)) for _ in query_ids]
             for _ in range(samples)] if len(query_ids) >= 2 else []
    comparisons = []
    for baseline, rows in by_mode.items():
        if baseline == "hybrid":
            continue
        if set(rows) != set(candidate):
            raise ValueError("Paired comparison requires identical query IDs")
        for metric in (f"recall@{k}", f"hit@{k}", f"mrr@{k}"):
            deltas = [candidate[q][metric] - rows[q][metric] for q in query_ids]
            estimates = sorted(sum(deltas[i] for i in draw) / len(draw) for draw in draws)
            interval = ([estimates[int(.025 * (samples - 1))],
                         estimates[int(.975 * (samples - 1))]] if estimates else None)
            comparisons.append({"candidate": "hybrid", "baseline": baseline, "metric": metric,
                                "queries": len(deltas), "mean_delta": sum(deltas) / len(deltas),
                                "percentile_95_interval": interval,
                                "wins": sum(d > 0 for d in deltas),
                                "ties": sum(d == 0 for d in deltas),
                                "losses": sum(d < 0 for d in deltas)})
    return {"method": "paired query bootstrap, percentile interval", "seed": seed,
            "resamples": samples if draws else 0, "comparisons": comparisons,
            "limitations": "Conditional on this corpus and supplied labels. Queries from the same "
            "video may be correlated. Intervals do not establish label validity, generalization, "
            "causality or significance across multiple comparisons. One query gives no interval."}
