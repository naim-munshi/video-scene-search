# Validation record

Validated in the hosted Linux/Python 3.12 environment recorded in
`validation-environment.json`. Apple Silicon/MPS and the user's own videos
were not accessible and were not tested.

| Check | Result | Scope |
| --- | --- | --- |
| Python compilation | PASS | Package, app and tests |
| Editable package installation / CLI help | PASS | Entry point and packaging |
| Core tests | PASS, 18 tests | Windows, RRF, metrics, rights gate, annotation validation and reports |
| Integration tests | PASS, 3 tests | Real OpenCV and FAISS, mocked ASR/embeddings, persistent reload, corruption rejection, Streamlit search/annotation |
| Streamlit empty-index state | PASS | Clear setup instructions without traceback |
| Real pretrained model smoke test | PASS | Whisper tiny CPU/int8, CLIP ViT-B/32 and multilingual MiniLM, synthetic 16s video with synthesized speech |
| Real-corpus Recall@5 comparison | NOT RUN | Needs permission-cleared videos and manually reviewed labels |
| Browser playback visually/audio reviewed | NOT RUN | AppTest validates video rendering metadata, not a human browser viewing/listening session |
| macOS / MPS runtime | NOT RUN | CPU/Linux checked only |

The real-model smoke test generated a red/blue MP4 with ffmpeg and a speech
track using flite. It verified eight frames, nonempty ASR segments, index
persistence and timestamped results from all three retrieval modes. It is a
wiring test, **not** semantic retrieval-quality evidence. No Recall@5 from
synthetic fixtures should be used on the CV or portfolio results table.

The first real-model run exposed `TypeError: open() got an unexpected keyword
argument 'metadata_errors'` with faster-whisper 1.2.1 and PyAV 19.0.2. Constraining
PyAV to the tested compatible range and installing 15.1.0 resolved this failure;
the same real-model smoke test then passed.

Reproduce:

```bash
python -m compileall -q src app.py tests
python -m unittest discover -s tests -v
RUN_INTEGRATION=1 python -m unittest discover -s tests -v
python scripts/real_model_smoke.py
```

The last command requires ffmpeg with libflite and cached/downloadable model
weights. Unit tests do not require downloads. Integration tests replace model
classes explicitly; the real-model script does not mock models.

Remaining acceptance work:

1. Add 2–3 permission-cleared, constant-frame-rate speaking videos.
2. Ingest with the chosen Whisper model (default base; smoke used tiny).
3. Review transcripts and timestamp alignment; verify playback in the Mac browser.
4. Write and manually annotate 24 queries before looking at rankings.
5. Use dev queries to fix configuration, then run held-out test evaluation.
6. Diagnose 3–5 actual failure cases and publish only measured results.
