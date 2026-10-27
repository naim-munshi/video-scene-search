# Video Scene Search — phased local portfolio completion / handoff

Last updated: 27 October 2026. Repo branch: MdNaim. Deployment: LOCAL MAC ONLY.
This document replaces the older synthetic-only completion checklist.

## Phase 1: Core retrieval and licensed portfolio corpus — IMPLEMENTED

- Three video sources recorded with attribution: NASA Apollo 15 (public-domain
  claim from hosting catalogue), ConversationEDU Steve Wozniak interview (CC BY
  3.0), Blender Foundation Tears of Steel (CC BY 3.0).
- Mac completed the three-video portfolio-real-v2 index: 41:48 footage, 252
  10-second search windows, 453 ASR speech segments.
- Faster-whisper speech recognition, 2-second frame sampling, CLIP visual
  embeddings, multilingual MiniLM transcript embeddings, FAISS indexes.
- Intent-weighted reciprocal rank fusion, window timestamps, representative
  thumbnails and video playback in Streamlit.
- Mac screenshot verified at least one NASA search result and playable
  timestamp. This is NOT a full browser/video acceptance sign-off.

## Phase 2: Development evidence and ranking — PARTIALLY VERIFIED

Mac terminal log confirmed successful OFFLINE evaluation with MPS workers,
six AI-assisted development queries, on 27 October 2026:

| Mode | Recall@5 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| Visual | 0.3722 | 0.6667 | 0.6667 |
| Transcript | 0.5167 | 0.6667 | 0.5417 |
| Hybrid | 0.6333 | 0.8333 | 0.8333 |

- Scores are from BEFORE the revised visual-intent keyword router added after
  this Mac run; no improved values are claimed until rerun.
- Original dev failures: q03 intro/name-caption visual target was missed by
  all three modes. q02 had 10 relevant windows, so exact Recall@5 cannot exceed
  5/10 = 0.50. Hybrid achieved stronger aggregate MRR, yet visual-kind query
  coverage remains a concern.
- The latest code expands visual-intent terms to include seated, captions,
  close-up, equipment, rover, gesture and other on-screen cues. This is a
  HYPOTHESIS/implementation change, not a measured improvement.
- Reports now disclose recall ceilings and AI-assisted weak-label provenance.
- The downloaded 24-query JSON contains candidate relevant window IDs and
  annotator provenance but was created using contact sheets and ASR. It is
  NOT independent human ground truth. Do not claim verified real-world accuracy.

## Phase 3: Reproducible release runner — IMPLEMENTED, MAC RUN REQUIRED

One command runs local index integrity checks, validates 6/18 query splits,
captures SHA-256 fingerprints for code/index/labels, evaluates dev and
provisional test split using cached models, and writes a shareable release ZIP
containing only JSON, CSV and Markdown evidence. Original media and source
indexes are neither modified nor included.

    cd ~/video-scene-search
    source .venv/bin/activate
    git pull --ff-only origin MdNaim
    python scripts/finish_portfolio.py --preflight-only
    python scripts/finish_portfolio.py --device mps

Default offline mode deliberately avoids the Hugging Face TLS certificate
error encountered on the user's Mac. No certificate checking is bypassed.
Each run chooses a new timestamped reports/portfolio-release-... directory.
If the model cache is missing or execution fails, the runner writes
RELEASE_STATUS.json with INCOMPLETE rather than fabricating metrics.

The output includes:
- RELEASE_SUMMARY.md: methodology, development/test scores, evidence caveats,
  pass/blocked gates and CV-safe project wording.
- dev/report.md, dev/metrics.csv and dev/per_query.json.
- test/report.md, test/metrics.csv and test/per_query.json.
- input-manifest.json with source/index fingerprint and audit evidence.
- shareable-release-evidence.zip containing JSON/CSV/Markdown only.

The weak-label test split is not scientific held-out ground-truth evaluation.
It may be run as an EXPLORATORY engineering check, never presented as a
human-labeled blind benchmark.

## Phase 4: Portfolio UX, documentation, and final evidence — IMPLEMENTED
## with non-code sign-offs remaining

- Streamlit search, Evaluate & annotate, Video Library and Add Videos tabs.
- Query picker defaults to q01 when labels exist; obvious AI-assisted label
  disclaimer and preserved annotation status.
- GitHub README includes truthful historical weak-label dev metrics, setup,
  architecture, source attribution and release runner.
- A reproducible no-video ZIP can be produced for sharing engineering evidence.
- New code has dependency-light GitHub CI tests. CI does NOT simulate Apple
  MPS, local copyrighted media, or Safari playback.

### External acceptance still needed for a professionally verified benchmark

1. A second person reviews relevance windows against actual video/audio.
   Sampled JPEG/ASR weak annotations are insufficient for independent claims.
2. On the Mac, verify search result and playback at matching timestamps for
   Interview, Tears of Steel and NASA; check console errors and missing media.
3. Record an attributed 60–90 second portfolio screen demonstration.
4. Run the one-command release script and keep its report archive.
5. Public cloud multi-tenant deployment would require user auth, private
   media isolation, quotas, retention and abuse controls; NOT provided by
   this local prototype.

## Release interpretation

LOCAL ENGINEERING PASS requires a successful three-video index audit,
query execution and both provisional report generations.
HUMAN-VERIFIED BENCHMARK remains NOT VERIFIED until independent label review.
BROWSER ACCEPTANCE remains NOT VERIFIED until three-video Safari check.
PRODUCTION-GRADE HOSTING remains OUT OF SCOPE.

None of the outstanding external checks blocks using the project as an
accurately-described local AI engineering PoC, but they block claiming a
fully human-verified performance benchmark or publicly secure SaaS.
