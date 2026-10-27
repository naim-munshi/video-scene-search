# Video Scene Search — Formal project closure

**Closure date:** 27 October 2026
**Release scope:** v0.1 local, single-user AI engineering portfolio prototype
**Release and default branch:** `main` (verified from repository metadata on 27 October 2026)
**Repository:** `naim-munshi/video-scene-search`
**Decision:** `CLOSED_LOCAL_ENGINEERING_SCOPE`

This means source-code implementation, automated testing, local three-video
indexing, 24-query exploratory evaluation, privacy constraints, portfolio
documentation, failure disclosure and a repeatable local handoff are
complete for the defined single-user PoC. It does NOT mean that Safari
media playback, independent ground truth or multi-user cloud security
have been independently certified.

## Phase closure matrix

| Phase | Gate | Closure decision | Grounding |
| --- | --- | --- | --- |
| P0 | Rights-aware source catalogue & architecture | COMPLETE | Three attributed video sources, pipeline/architecture documentation |
| P1 | Ingestion, frame+ASR embeddings, FAISS, UI search and timestamps | COMPLETE | Three-video indexed Mac corpus and screenshot demonstration of NASA playback |
| P2 | Batch development evaluation, transparent retrieval/failure analysis | COMPLETE, EXPLORATORY | 6 dev candidate weak-label queries; per-query errors and recall ceilings |
| P3 | Repeatable full local engineering release | PASS | Mac `LOCAL_ENGINEERING_CHECKS_PASS`: index hashes, 6 dev + 18 provisional test queries |
| P4 | Safe local media validation and guided Safari checklist | **LOCAL MEDIA PASS**; Safari self-attestation pending | Real three-source FFmpeg decode passed; nine-step browser checklist implemented |
| P5 | Final README, architecture, limitations, demo storyboard, CV description | COMPLETE | Version-controlled documentation and release audit |

## Verified engineering facts

- The owner's supplied Mac release confirms 3 source videos, 252 indexed
  windows, 1,256 sampled frames, 453 ASR speech segments, zero index-audit
  warnings, and successful CLIP/MiniLM evaluation under MPS.
- Audit build SHA-256:
  `8d1f6c43f94d5cf39002ae48caade0b181189948723c0e71019ec962a83a1842`.
- Source code and unit tests run under GitHub Actions CI; their results are
  software tests, not actual video recognition or Apple MPS browser tests.
- The Mac release includes `RELEASE_SUMMARY.md`, `RELEASE_STATUS.json`,
  dev/test metrics, per-query windows and an archive of textual evidence.
- 18-query provisional Hybrid Recall@5 = 0.5224, Hit@5 = 0.7222,
  MRR@5 = 0.5759, **only against AI-assisted weak labels**.
- Relevant content IDs and model predictions were cross-checked for
  arithmetic consistency. This is NOT independent semantic ground truth.

## Open external sign-offs (do not misrepresent as completed)

1. `LOCAL_MEDIA_DECODE`: **PASS on the owner's Mac**, from 27 Oct 2026
   report `reports/media-preflight-20261027-145120.json`. All three original
   sources had H.264/AAC, actual beginning/middle/near-end decoded video
   frames and a decoded audio excerpt. This is a native media integrity check,
   not Safari/browser acceptance.
2. `SAFARI_BROWSER`: the actual operator must check video and sound at
   Beginning/Middle/Near end in the three original sources. The app now
   preserves confirmations across source and timestamp changes and
   generates a JSON of **USER_SELF_ATTESTED** results only after all nine
   boxes are checked and source videos remain present; incomplete sessions
   remain `NOT_VERIFIED`.
3. `INDEPENDENT_BENCHMARK`: the 24 candidate labels came from sampled
   contact sheets and ASR. An independent reviewer checking raw footage
   and a new untouched test set are necessary for credible statistical
   performance claims. The original test queries have already been
   inspected, so they cannot be treated as newly blind.
4. `PUBLIC_DEMO_RECORDING`: source video clips/audio are not included in
   the repo. `docs/DEMO_RECORDING.md` gives a reproducible recording plan;
   a finished, rights-cleared recording is not claimed.
5. `MULTIUSER_PRODUCTION`: authentication, per-user media privacy, secure
   uploads, quotas, retention and a threat-modelled deployment are out of
   scope. Do not host this app for external accounts without a new project.

## Exact final local instructions (no re-ingestion, no retraining)

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin main
python scripts/media_playback_preflight.py --index artifacts/portfolio-real-v2
SCENE_INDEX=artifacts/portfolio-real-v2 python -m streamlit run app.py --server.address 127.0.0.1
```

Then, only if operator validation is desired, visit the Video library
tab and perform nine manual playback checkpoints. Do not rerun the
24-query weak-label test simply to generate another identical report.
The previously accepted release artifact remains under
`reports/portfolio-release-20261027-132941/` on the owner's Mac.

## Read-only evidence cross-check

Use `python scripts/final_acceptance.py` after the earlier successful
release and media preflight. It checks the previously stored 6/18
query split, weak-label provenance, original three-video media decode
evidence and optional nine-point operator playback self-attestation.
Missing, inconsistent or unrelated evidence is rejected; no pass is
claimed from GitHub-only tests. It never modifies source/index/reports.
The resulting status before optional manual Safari review is
`LOCAL_ENGINEERING_PASS_BROWSER_PENDING`.

## Portfolio-ready claim

**Safe description:** Developed a local multimodal video scene retrieval
prototype with timestamped playback, faster-whisper ASR, CLIP vision
embeddings, multilingual MiniLM text embeddings, FAISS and weighted
reciprocal rank fusion. Indexed 3 source-attributed videos and produced
auditable exploratory 24-query engineering evaluations with explicit
weak-label and privacy limitations.

**Do not claim:** independently verified 52.24% accuracy, production-ready
hosting, complete 9-point Safari sign-off, or a published demo recording
until those specific external tasks are actually completed.

## Repository freeze policy

Do not alter the historical dev/test results or add multimedia to Git.
Additional tuning should be planned as a new experimental phase with
a fresh held-out test set and provenance-aware annotations. The v0.1
local engineering scope is otherwise concluded.

Technical references: `docs/ARCHITECTURE.md`,
`docs/LOCAL_RELEASE_RESULTS_2026-10-27.md`,
`docs/SECURITY_REVIEW.md`, `docs/DEMO_RECORDING.md`.
