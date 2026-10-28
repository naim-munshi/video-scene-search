# Video Scene Search v0.1.0 — Local AI Engineering Portfolio

**Release status:** Local single-user engineering prototype complete.

Video Scene Search is a multimodal video retrieval proof of concept that finds
timestamped moments in video using natural-language descriptions of the image
or speech. This release contains source code, documentation, CI and a small
real-app screenshot gallery; **original video files, model weights, transcripts,
private relevance labels and FAISS indexes are not distributed**.

## Shipped capabilities

- faster-whisper ASR, sampled video frames, CLIP ViT-B/32 visual embeddings
  and multilingual MiniLM transcript embeddings.
- Normalized FAISS similarity search and intent-weighted reciprocal rank
  fusion across visual and speech evidence.
- Local Streamlit interface with mode selection, timestamp playback,
  representative frames, transcript evidence, video library and annotation.
- Incremental indexing, local evidence/integrity checks, offline cached-model
  evaluation, non-destructive reporting and human playback self-attestation.
- Three permission-attributed video sources (NASA Apollo 15, Blender
  *Tears of Steel*, ConversationEDU interview), 252 indexed windows,
  1,256 sampled frames and 453 ASR speech segments on the owner's Mac.
- Tested local H.264/AAC media decoding on all three source clips.

## Evaluation (AI-assisted weak labels only)

The development split (6 queries) and provisional test split (18 queries)
were successfully executed on the original Mac corpus. The following
numbers are **exploratory sanity-check measurements**, not independently
human-verified real-world model accuracy:

| Method | Dev Recall@5 | Dev MRR@5 | Provisional test Recall@5 | Provisional test MRR@5 |
| --- | ---: | ---: | ---: | ---: |
| Visual | 0.3722 | 0.6667 | 0.3925 | 0.4676 |
| Transcript | 0.5167 | 0.5417 | 0.4159 | 0.4167 |
| Hybrid | 0.6333 | 0.8333 | 0.5224 | 0.5759 |

Hybrid Hit@5 on provisional test: 13/18 queries. The original test set
has already been inspected, so further tuning will require fresh held-out
queries for a defensible blind comparison.

## Software quality

- GitHub Actions: Python 3.10, 3.12, 3.13; unit tests and tracked-file
  privacy guard (the tag publication workflow repeats checks).
- Local engineering release: `LOCAL_ENGINEERING_CHECKS_PASS`.
- Native source-media preflight: `LOCAL_MEDIA_DECODE_PASS`.
- Public cloud / multi-user security: **not supported**.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m streamlit run app.py --server.address 127.0.0.1
```

Provide your own source videos and license/attribution manifest, or run
the included synthetic demo. The owner's original three-video index is
not included in this release.

## Honest release limitations

- Independent human-verified labels: **NOT VERIFIED**.
- All nine Safari playback checkpoints (manual): **NOT VERIFIED** until
  the operator signs off on picture and sound.
- Recorded and published demo video: not included.
- Production authentication/multi-tenant isolation: **OUT OF SCOPE**.

Screenshots are genuine local UI captures supplied by the owner, with
source credit and legal reuse caveats in `docs/DEMO_GALLERY.md`.
See `docs/PROJECT_CLOSURE.md`, `docs/LOCAL_RELEASE_RESULTS_2026-10-27.md`
and `SECURITY.md` for scope, evaluation and safeguards.

**Version:** v0.1.0. This is a finished local portfolio implementation,
not an independently certified accuracy benchmark or production SaaS.
