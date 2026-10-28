# Human review and fresh evaluation

This workflow creates a new, auditable evaluation set without overwriting the
existing index or historical weak-label results. It does **not** generate ground
truth, certify human independence, or turn old test queries into an unseen test.
All commands run from the repository root with the existing environment active.
No re-ingestion, training or model download is needed if the current index and
model cache are available.

## 1. Write fresh queries before viewing rankings

```bash
scene-search init-labels --index artifacts/portfolio-real-v2 \
  --count 48 --dev-count 12 --output evaluation/fresh-draft.json
```

The suggested small study has 12 dev and 36 test queries, balanced across visual,
speech and mixed queries. This is a practical starting point, not a sufficient
sample size for population-wide accuracy claims. Use more independent videos
when possible; queries from the same video are correlated. Existing 24-query
commands remain supported by the CLI defaults.

Edit **only** each query's `text` and, if necessary, `kind`/`split` in the JSON.
Write specific, answerable questions from watching the source footage, without
looking at search results. Avoid copying or paraphrasing the already inspected
24-query set. Keep relevant IDs empty at this stage.

For Japanese applications, include a separately identified Japanese-query study
only if you can review its labels. The current CLIP visual encoder and English
intent heuristic do not establish Japanese retrieval quality. Do not mix languages
and claim a language-specific result without separate reporting.

## 2. Freeze the query plan

```bash
scene-search freeze-labels --index artifacts/portfolio-real-v2 \
  --labels evaluation/fresh-draft.json --output evaluation/fresh-plan.json
```

If the old label file is available, add `--exclude-labels PATH_TO_OLD_LABELS.json`
before executing the command. Repeat the option for other inspected sets. This
rejects exact normalized text reuse, including case/spacing/full-width changes;
it does **not** detect paraphrases or prove that a query was unseen.

Archive the plan before experiments, ideally with your supervisor/reviewer. Its
hash binds query IDs/text/types/splits to the index build. It detects accidental
drift against that retained plan, not intentional rewriting of both files.
The CLI refuses to overwrite an existing plan.

## 3. Watch and label without ranked search results

Use a local video player or the app's **Video library** tab to browse source
timestamps. Do not run searches for test questions. `windows.json` in the index
maps each ID to its video and start/end time. Review **all** potentially relevant
windows, not only model-returned candidates. ASR and sparse frames can miss facts;
watch/listen to the original source for the final decision.

In `fresh-draft.json`, fill `relevant` and `review` for each frozen query:

```json
{
  "id": "q01",
  "text": "YOUR PREVIOUSLY FROZEN QUERY",
  "kind": "visual",
  "split": "dev",
  "relevant": ["ACTUAL_VIDEO_ID:00012"],
  "review": {
    "reviewed": true,
    "reviewer": "reviewer-A",
    "evidence_note": "Describe the visible or audible evidence and timestamps."
  }
}
```

This is a schema example, **not a completed annotation**. Use a reviewer alias,
not private contact details. Keep frozen fields and their order unchanged. The
legacy **Evaluate & annotate** editor is for exploratory labels; it does not
preserve this new frozen protocol's review metadata, so edit the fresh JSON file
directly. Save work locally throughout review.

At least one relevant window is required. This benchmark is deliberately
**answerable-query retrieval**, not abstention evaluation. If a question is
ambiguous or truly unanswerable, record why and start a revised version of the
plan **before evaluation**; never invent a positive label or drop a failed query
after viewing results. Keep unanswerable queries for a separate future study.

Prefer a second reviewer for the test set or a subset, resolve disagreements
against the source video, and describe that process in the final report. The
software records declarations but cannot verify who actually did the work.

## 4. Validate the completed human review

```bash
scene-search finalize-labels --index artifacts/portfolio-real-v2 \
  --labels evaluation/fresh-draft.json --plan evaluation/fresh-plan.json \
  --output evaluation/fresh-reviewed.json
```

Finalization rejects missing reviewer/evidence notes, unreviewed queries, unknown
window IDs, duplicate text, changed frozen fields, a changed plan hash or stale
index hashes. It writes a separate file classified as **human review
self-reported**, with independent ground truth left **unknown**. A successful
command is not independent certification of model accuracy.

## 5. Compare four methods with the same candidates

```bash
scene-search evaluate --index artifacts/portfolio-real-v2 \
  --labels evaluation/fresh-reviewed.json --plan evaluation/fresh-plan.json \
  --split dev --compare-equal-rrf --offline --output reports/fresh-dev-v1
```

Compare visual-only, transcript-only, equal-weight RRF and the existing
intent-weighted hybrid. Equal RRF is a **control**: it shows whether the added
English intent heuristic helps or hurts compared with simple fusion. Adding the
control changes the report only; it does not change the app's rankings.

After making decisions on dev, freeze the code/configuration and evaluate test:

```bash
scene-search evaluate --index artifacts/portfolio-real-v2 \
  --labels evaluation/fresh-reviewed.json --plan evaluation/fresh-plan.json \
  --split test --compare-equal-rrf --offline --output reports/fresh-test-v1
```

The offline flag requires both model caches. It fails instead of downloading a
missing model. Use a new output path for every report. Do not select the best
test run or adjust the heuristic on this test set and keep calling it unseen.

## Read the results

| File | What to inspect |
| --- | --- |
| `metrics.csv` | Macro Recall@K, Hit@K and MRR@K, overall and by query type |
| `per_query.json` | Actual predictions, relevant windows, misses and false positives |
| `comparisons.json` | Paired hybrid-minus-baseline deltas, wins/ties/losses and seeded 95% bootstrap intervals |
| `evidence.json` | Build/label/plan hashes, code hashes, label provenance and runtime context |
| `report.md` | Comparison tables, recall ceilings and failure-review prompts |

Intervals resample paired queries 2,000 times with seed 42. They are conditional
on these labels, do not correct annotation errors or within-video dependence,
and are not proof of generalization or statistical significance across multiple
comparisons. One query yields no interval. Timing is amortized batch runtime
including model startup, **not** interactive p95 query latency.

Record 3–5 failures: ASR omission, missed sampled frame, ambiguous wording,
incorrect annotation, or fusion demotion. Check the source before assigning a
cause. A negative or mixed result is useful evidence; do not hide it.

## বাংলা সংক্ষিপ্ত নির্দেশনা

1. নতুন ৪৮টি প্রশ্ন লিখবে; পুরোনো ২৪টি প্রশ্ন copy করবে না।
2. Search result দেখার আগে `freeze-labels` চালাবে।
3. মূল ভিডিও দেখে `relevant`, reviewer alias ও evidence note পূরণ করবে।
4. `finalize-labels` দিয়ে যাচাই করবে। এটি মানুষের review-এর ঘোষণা, স্বাধীন প্রমাণ নয়।
5. Dev-এ সিদ্ধান্ত নেবে; তারপর fixed code দিয়ে test চালাবে।
6. সব local labels/reports private থাকবে; README-তে কেবল যাচাই করা summary দেবে।
