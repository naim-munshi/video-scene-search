# Demo, retrieval evaluation, and portfolio acceptance

There are **two independent tracks**. Do not combine their measurements.

## A. Reproducible synthetic demo (no third-party footage)

Runs on a Mac or Linux machine with FFmpeg compiled with `flite`, Python
3.10–3.13, and project dependencies (`pip install -e .`). Some standard macOS
FFmpeg builds may lack flite; check `ffmpeg -filters | grep flite` and use a
compatible build or record your own speech. Model weights download on first use.

```bash
python scripts/synthetic_demo.py generate
scene-search ingest --manifest data/demo-corpus.json --output artifacts/demo-index --whisper-model tiny --language en
python scripts/synthetic_demo.py labels --index artifacts/demo-index
scene-search evaluate --index artifacts/demo-index --labels evaluation/demo-labels.json --split dev --output reports/demo-dev
scene-search evaluate --index artifacts/demo-index --labels evaluation/demo-labels.json --split test --output reports/demo-test
SCENE_INDEX=artifacts/demo-index python -m streamlit run app.py --server.address 127.0.0.1
```

The generator produces 3 short 30-second MP4s, each with three ten-second
solid-color scenes and synthesized English speech. Video files live under
`data/`, and all built artifacts, reports and labels stay out of GitHub. The
queries are deterministic **synthetic ground truth**, not independent human
judgment. The test labels cover 18 queries, dev covers 6; do not use these
results as evidence of real-world Recall@5 or hiring claims.

Try searching for `a red screen`, `project deadline`, and
`a green scene while a narrator discusses financial budget`; open the exact
moment and listen. The output of a model may be wrong; don't assume these
queries must all rank first. A demonstration should show both successes and
failures. If it cannot index, note the actual error instead of fabricating
metrics. The generated audio is synthetic voice, not human conversation.

## B. Actual video acceptance (needed before reporting quality)

1. Obtain 2–3 **permission-cleared** videos with audible conversations, each
   roughly 10–20 minutes. Record the source, exact license, attribution and
   participant consent, if applicable, in the manifest. These files are not
   provided with this repository. Never upload private video or transcripts
   without permission.
2. Place clips in `data/videos/` and update `examples/corpus.json`.
   Change `rights_confirmed` to `true` only if verified. Inspect licenses
   manually; the flag is not legal validation.
3. Verify metadata and audio tracks:

   ```bash
   python scripts/real_video_preflight.py --manifest examples/corpus.json
   ```

   This checks 2–3 sources, 600–1200 seconds each, a video and an audio stream,
   frame-rate metadata, and video codec. It cannot prove speech is intelligible,
   that frames match timestamps, or that recording/redistribution is permitted.
4. Ingest and validate playback locally:

   ```bash
   scene-search ingest --manifest examples/corpus.json --output artifacts/real-v1 --language en
   SCENE_INDEX=artifacts/real-v1 python -m streamlit run app.py --server.address 127.0.0.1
   scene-search init-labels --index artifacts/real-v1 --output evaluation/real-labels.json
   ```

   Review start/middle/end positions of all clips; inspect transcripts and
   representative frames, including a silent stretch. Check search timestamps
   against what a person can see/hear. Do not expose the local Streamlit app
   on a public server, since it can display private videos.
5. Before checking ranked results, write 24 distinct queries (8 visual,
   8 speech, 8 mixed), label **all** relevant 10-second windows, save complete
   annotations, reserve 6 queries for dev and 18 for test. Do not inspect
   test-ranked results while tuning.
6. Evaluate and retain the report files locally:

   ```bash
   scene-search evaluate --index artifacts/real-v1 --labels evaluation/real-labels.json --split dev --output reports/real-dev-v1
   scene-search evaluate --index artifacts/real-v1 --labels evaluation/real-labels.json --split test --output reports/real-test-v1
   ```

   The evaluator outputs Recall@5, Hit@5 and MRR@5 for visual, transcript and
   hybrid, per-kind breakdowns, per-query misses/false positives, and hashes
   tracing reports to build and label files. The test split is evaluated only
   once after fixing the search configuration using dev. Report per-query
   weaknesses and label uncertainty: on a small corpus there may be several
   acceptable scenes or unlabelled positives.
7. Record a 60–90-second demo with permission-cleared media. Show the app,
   three modality queries, playback jumping to real timestamps, one miss,
   and the real result table. A screenshot/GIF should contain no private
   voices, faces, titles or transcripts unless licensed to share.

## Evidence / release gates

| Gate | Evidence | Current state |
| --- | --- | --- |
| Code compiles and pure tests pass | GitHub Actions core job | Automated |
| Three synthetic 30s MP4s generated with speech | `test_demo.py` on FFmpeg/flite hosts | Automated where supported |
| Native FAISS/OpenCV/UI integration | Opt-in `RUN_INTEGRATION=1` | Needs full ML install |
| Real pretrained-model ingestion | `scripts/real_model_smoke.py` | Previously validated on Linux per `docs/VALIDATION.md`; rerun locally |
| 2–3 authentic 10–20min video recordings | Media with provenance and confirmed permission | **Not supplied** |
| Manual annotation and real-data Recall@5 | `reports/real-test-v1/` | **Not measured** |
| Demo with real scenes | Licensed screen capture and timing checks | **Not recorded** |

**Portfolio wording until actual evaluation is complete:**

> Built a local multimodal video retrieval proof of concept using faster-whisper,
> CLIP and FAISS, with visual, transcript and RRF-hybrid search, timestamped
> playback, synthetic integration fixtures and an auditable evaluation pipeline.

Do not substitute synthetic benchmark numbers for real-video results. Media files,
indexes, annotation files, model caches and local reports are excluded from git.
