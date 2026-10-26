# Project completion checklist (local portfolio release)

## Proven from actual Mac logs (26 October 2026)

- Synthetic demo generation: three locally generated 30-second videos
- FFmpeg 9.0.2 available on Apple Silicon
- Mac Python 3.12 environment and dependencies installed
- Index was completed at `artifacts/demo-index-isolated/build.json`
- Query workers on MPS successfully returned transcript and hybrid results
- Streamlit started on `127.0.0.1:8501`
- **Pre-routing 6-query synthetic dev baseline:** Visual Recall@5
  0.6667 / MRR@5 0.6667; transcript 1.0000 / 1.0000;
  equal-weight hybrid 0.8333 / 0.7500

## Changed after that baseline

- Hybrid now selects transparent rank weights by query-intent cues
- The evaluator uses exactly the same `hybrid_fuse` function as live search
- Added metadata/index consistency check and security documentation

**These changes require a fresh Mac dev evaluation.** None of the above
baseline numbers represents a measured improvement of the new fusion policy.

## Local release acceptance

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/acceptance_check.py --index artifacts/demo-index-isolated \
  --query "project deadline" --device mps
scene-search evaluate --index artifacts/demo-index-isolated \
  --labels evaluation/demo-labels-isolated.json --split dev \
  --output reports/demo-dev-intent-v1 --device mps
cat reports/demo-dev-intent-v1/report.md
```

Do not regenerate/rebuild the original demo video or overwrite the saved
baseline report. If any output path already exists, create a new one.

## Not reproducibly complete without user-owned media or observation

- 2–3 licensed/consent-checked real talking videos, 10–20 min each
- Metadata preflight, recording/audio/transcript review
- 24 manually annotated queries with frozen 6/18 dev/test split
- **One held-out** real-video test evaluation after model/fusion selection
- Recall@5, MRR@5, error analysis and honest limitations from real content
- 60–90 second screen recording that demonstrates timestamped playback
- Additional security review for public hosting (not in scope for local portfolio)

Do not put made-up accuracy, fake dataset provenance or synthetic-only
numbers on a CV as measured real-world performance.

## Finished vs unfinished

The **local synthetic proof-of-concept and code** are complete enough for a
portfolio demonstration and CI checks. A **real-world retrieval evaluation**
and production-grade deployment are separate gates and remain incomplete.
