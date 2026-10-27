# Changelog

This repository follows a lightweight changelog convention. Entries describe implemented work and **do not** imply independently human-verified retrieval accuracy.

## [Unreleased]

- Professional `main`-branch repository presentation, contribution and security documentation.
- Local video/audio decoder checkpoint verification and optional operator playback checklist.
- Source and documentation polish; no retraining or modification of local videos/indexes.

## [0.1.0] — 2026-10-27

### Added

- Indexed natural-language scene search via CLIP ViT-B/32, faster-whisper, MiniLM, FAISS and intent-weighted RRF.
- Timestamped Streamlit playback, local media library, query annotation and metadata-aware local import staging.
- Three source-attributed local videos: 252 search windows, 1,256 frames, 453 transcribed speech segments.
- Integrity-checked build manifests, Mac MPS query workers and an offline cached-model mode.
- Reproducible 24-query **AI-assisted weak-label** exploratory evaluation and per-query failure reports.
- Non-destructive engineering release generator including dev/test reports and evidence archive.
- Mac H.264/AAC FFmpeg spot-decoding preflight for all three sources.

### Verified scope

- The owner's Mac returned `LOCAL_ENGINEERING_CHECKS_PASS` for the v0.1 local software release and `LOCAL_MEDIA_DECODE_PASS` for the three source files.
- Against **AI-assisted weak labels only**, provisional 18-query Hybrid Recall@5 was 0.5224, Hit@5 0.7222 and MRR@5 0.5759.
- Independent ground truth, full Safari playback sign-off, demo video publication and secure public hosting were **not** certified.

See [full release analysis](docs/LOCAL_RELEASE_RESULTS_2026-10-27.md) and [project closure](docs/PROJECT_CLOSURE.md).
