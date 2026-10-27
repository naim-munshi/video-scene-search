# Video Scene Search — phased local portfolio completion / handoff

Last updated: 27 October 2026. Release branch: main. Deployment: LOCAL MAC ONLY.
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

- The earlier dev measurements preceded the revised visual-intent router.
  The owner's subsequent Mac release produced identical dev aggregates;
  therefore no measurable aggregate improvement is claimed.
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

## Phase 3: Reproducible release runner — MAC ENGINEERING PASS

One command runs local index integrity checks, validates 6/18 query splits,
captures SHA-256 fingerprints for code/index/labels, evaluates dev and
provisional test split using cached models, and writes a shareable release ZIP
containing only JSON, CSV and Markdown evidence. Original media and source
indexes are neither modified nor included.

    cd ~/video-scene-search
    source .venv/bin/activate
    git pull --ff-only origin main
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

The Mac run succeeded on 27 October 2026. Release status was
`LOCAL_ENGINEERING_CHECKS_PASS` after index verification and both 6-query
development and 18-query provisional test execution. Weak-label test scores:
visual Recall@5/MRR@5 0.3925/0.4676, transcript 0.4159/0.4167,
hybrid 0.5224/0.5759. Test hybrid Hit@5 0.7222 (13 of 18 queries).
Metric arithmetic and archive content were checked independently using the
uploaded per-query evidence; see docs/LOCAL_RELEASE_RESULTS_2026-10-27.md.
These test scores are AI-assisted WEAK-LABEL results, not scientifically
independent ground-truth performance. The test split has now been inspected
and is no longer untouched for any future tuning.

## Phase 4: Portfolio UX, documentation, and final evidence — IMPLEMENTED
## with non-code sign-offs remaining

- Streamlit search, Evaluate & annotate, Video Library and Add Videos tabs.
- Query picker defaults to q01 when labels exist; obvious AI-assisted label
  disclaimer and preserved annotation status.
- GitHub README includes truthful historical weak-label dev metrics, setup,
  architecture, source attribution and release runner.
- A reproducible no-video ZIP can be produced for sharing engineering evidence.
- A local `scripts/media_playback_preflight.py` checks that all three
  existing source MP4s have H.264/AAC streams and emits actual FFmpeg
  framehash rows at beginning/middle/end and for a short audio excerpt.
  Its code has CI tests, but the original media still requires the owner's
  Mac for native execution.
- Video Library now includes a three-timestamp playback selector and a
  nine-checkbox Safari/picture/sound self-attestation download; an unchecked
  or incomplete checklist reports NOT_VERIFIED. User self-attestation is
  not independent browser certification.
- New code has dependency-light GitHub CI tests. CI does NOT simulate Apple
  MPS, local copyrighted media, or Safari playback.

### External acceptance still needed for a professionally verified benchmark

1. A second person reviews relevance windows against actual video/audio.
   Sampled JPEG/ASR weak annotations are insufficient for independent claims.
2. On the Mac, verify search result and playback at matching timestamps for
   Interview, Tears of Steel and NASA; check console errors and missing media.
3. Record an attributed 60–90 second portfolio screen demonstration,
   if one is needed for publication; see docs/DEMO_RECORDING.md.
4. Release script already ran successfully; preserve the existing report
   archive in reports/portfolio-release-20261027-132941.
5. Public cloud multi-tenant deployment would require user auth, private
   media isolation, quotas, retention and abuse controls; NOT provided by
   this local prototype.

## Release interpretation

Formal closed scope: `CLOSED_LOCAL_ENGINEERING_SCOPE` as defined in
[PROJECT_CLOSURE.md](PROJECT_CLOSURE.md); this is not a human-verified
benchmark or secure public production service.


LOCAL ENGINEERING PASS confirmed by the supplied Mac release evidence:
three-video index audit, query execution and both provisional reports.
HUMAN-VERIFIED BENCHMARK remains NOT VERIFIED until independent label review.
BROWSER ACCEPTANCE remains NOT VERIFIED until three-video Safari check.
PRODUCTION-GRADE HOSTING remains OUT OF SCOPE.

None of the outstanding external checks blocks using the project as an
accurately-described local AI engineering PoC, but they block claiming a
fully human-verified performance benchmark or publicly secure SaaS.
