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
git pull --ff-only origin MdNaim
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
