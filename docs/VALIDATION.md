# Validation record — updated 27 October 2026

## Real-video evidence from the owner's Mac (27 October 2026)

- Three source-attributed videos were processed into portfolio-real-v2:
  252 fixed ten-second windows, 453 speech segments and approximately
  41:48 combined playback duration.
- Mac/Safari screenshot verified NASA scene search and playback.
  This is not a full three-video Safari/browser sign-off.
- The user's Mac successfully completed an **offline**, six-query,
  development-only exploratory evaluation using real CLIP and MiniLM
  model workers with MPS. This used AI-assisted weak relevance labels:

| Mode | Recall@5 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| Visual | 0.3722 | 0.6667 | 0.6667 |
| Transcript | 0.5167 | 0.6667 | 0.5417 |
| Hybrid | 0.6333 | 0.8333 | 0.8333 |

**Warning:** This is not independently verified real-world accuracy.
The development numbers precede the new visual-intent keyword update.
No improvement can be asserted until a new local Mac evaluation is run.
The subsequent local release runner **did complete 18 provisional test
queries** with the updated code: visual Recall@5/MRR@5 0.3925/0.4676,
transcript 0.4159/0.4167, hybrid 0.5224/0.5759; hybrid Hit@5 0.7222.
These are AI-assisted weak-label measurements, not human-reviewed
blind-test accuracy. The complete audit and per-query failure review is
at [Local release results](LOCAL_RELEASE_RESULTS_2026-10-27.md).
q02's ten labeled candidate windows imply maximum Recall@5 = 0.5.
q03 missed its labeled interview opening in all three modes.

## Current repository release readiness

- The release runner has now succeeded on the owner's Mac; its
  RELEASE_STATUS.json reports LOCAL_ENGINEERING_CHECKS_PASS and the
  independent arithmetic/ZIP audit found no inconsistencies.
- A release runner under scripts/finish_portfolio.py checks local index
  metadata, 24-query label shape (6 dev + 18 test), SHA-256 build/index
  fingerprints, executes both splits with local cached models, creates
  Markdown/CSV/JSON reports and a shareable evidence ZIP without video files.
- Online TLS certificate verification is not disabled; the default is
  offline cached Hugging Face models.
- The release script is validated by dependency-light GitHub CI unit tests.
  GitHub CI does not run Apple MPS or original source videos and cannot
  verify the user's Mac runtime, actual relevance, or Safari interactions.
- Query annotation UI shows an explicit weak-label disclaimer.
- See docs/PORTFOLIO_COMPLETION.md for phase status and the exact command.

---

# Validation record — October 26, 2026

## Latest GitHub Actions

The verified core run at commit `6774107` compiled the Python source,
app, scripts and tests, then ran **51 tests: 46 passed, 5 skipped**.
The five skips cover optional FFmpeg and native ML integration checks in
the lightweight CI environment. These automated counts are not
measurements of model accuracy.

The tests cover windows, rights checks, annotation integrity, RRF fusion,
batch evaluator behavior, worker crash containment, metadata validation,
index integrity and timestamp sampling.

## User Mac evidence

On Apple Silicon / macOS 26.5.2, Python 3.12 and FFmpeg 9.0.2, the supplied
terminal logs confirm:
- Three 30-second synthetic MP4 videos with synthesized speech were generated
- The completed synthetic index was found on disk
- Transcript and hybrid search returned timestamped results via MPS workers
- Streamlit started on loopback at 127.0.0.1:8501
- The **old equal-weight** model on six synthetic development queries achieved
  visual Recall@5/MRR@5 0.6667/0.6667, transcript 1.0/1.0,
  hybrid 0.8333/0.75

These are synthetic deterministic labels, **not real-world quality
metrics**. The intent-aware hybrid routing and batch evaluation changes
were introduced after the measurements, so their Mac accuracy and runtime
are not verified by these older logs. A working web server does not
establish human-verified playback.

## Historical Linux smoke

The reference `validation-environment.json` documents an earlier hosted
Linux test of an older OpenCV version. Its 18 core and 3 optional mocked
integration checks passed, as did a small synthetic real-model smoke.
That environment does not validate the revised PyAV/MPS implementation.

The earlier faster-whisper/PyAV 19 incompatibility was addressed by
constraining PyAV to version <16. The new smoke script supports an
existing index and does not require FFmpeg's optional flite filter.

## Reproduce on Mac

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin main
python -m pip install -e .
python -m compileall -q src app.py scripts tests
python -m unittest discover -s tests -v
python scripts/acceptance_check.py --index artifacts/demo-index-isolated
python scripts/real_model_smoke.py --index artifacts/demo-index-isolated --device mps
scene-search evaluate --index artifacts/demo-index-isolated \
  --labels evaluation/demo-labels-isolated.json --split dev \
  --output reports/demo-dev-intent-v1 --device mps
```

The metadata checker is pure Python. The smoke script exercises real
pretrained models and isolated workers but does not measure semantic
accuracy. Optional full native integration tests can be run with
`RUN_INTEGRATION=1 python -m unittest discover -s tests -v` when ML
dependencies are installed; they have not been rerun in the current
user Mac evidence.

## Remaining release gates

1. Repeat development evaluation on the new hybrid ranking policy.
2. Watch and listen to timestamped playback in the actual browser.
3. Evaluate 2–3 permission-cleared 10–20-minute real conversation videos.
4. Manually annotate 24 queries (6 dev and 18 held-out test), before
   inspecting their rankings.
5. Freeze the configuration and run the held-out real-video test once.
6. Record a short demo using footage/audio licensed for publication.
7. Build authentication, isolation, quotas and privacy operations before
   hosting for multiple users.

Current scope: **working local synthetic proof of concept, not a validated
production system**.
