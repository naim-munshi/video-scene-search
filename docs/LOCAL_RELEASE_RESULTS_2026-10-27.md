# Local portfolio release audit — 27 October 2026

## Evidence and reproducibility

This document summarizes local Mac release outputs supplied by the project owner.
It does not assert independent visual ground truth or SaaS security.

- Release path: `reports/portfolio-release-20261027-132941` (on the owner's Mac)
- Local release status: `LOCAL_ENGINEERING_CHECKS_PASS`
- Input platform: macOS 26.5.2, arm64, Python 3.12.4
- Original three-video corpus: NASA Apollo 15, Steve Wozniak interview, Tears of Steel
- Integrity audit: `metadata_integrity_passed`; 3 videos, 252 windows, 1,256 sampled frames, 453 speech segments, zero missing-source warnings
- Build SHA-256: `8d1f6c43f94d5cf39002ae48caade0b181189948723c0e71019ec962a83a1842`
- Label SHA-256: `af0f5c056cafc67f55f06a56c2ca589ab81aaf9e50811552348c817ca13d2f4c`
- Attached local evidence ZIP SHA-256: `afa479577227f9092cb06f4438f1baa76d132a586dbf8cc66ccf3cb8b45c6bc9`
- Provenance: `assistant_assisted_contact_sheets_and_asr`, `independently_verified: false`

All three separate release files matched the copies in the ZIP exactly.
The `testzip()` ZIP integrity check passed. The stored per-query predicted
window IDs and relevant sets were used to independently recalculate
Recall@5, Hit@5, MRR@5 and every macro CSV aggregate; no arithmetic
inconsistency was detected.

**Evaluation caveat:** these are AI-assisted WEAK labels, selected from
representative frames and ASR, without independent human validation of
every relevant interval or complete raw audio/video. The numbers below
are **preliminary sanity-check measurements** for the small local corpus.
Because the test split has now been inspected, future tuning against its
failures would invalidate a claim of blind held-out performance.

## Development metrics (6 queries)

| Method | Recall@5 | Hit@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| Visual | 0.3722 | 0.6667 | 0.6667 |
| Transcript | 0.5167 | 0.6667 | 0.5417 |
| Hybrid | 0.6333 | 0.8333 | 0.8333 |

- `q03` interview title/name-caption opening: no labeled window in top five
  for any of visual/transcript/hybrid search.
- `q02` has 10 labeled candidate windows and maximum Recall@5 = 0.5 by
  definition; this is a benchmark-design limitation, not always a retrieval
  failure. Visual retrieval achieved more `q02` hits than hybrid.
- This development result is numerically identical to the earlier Mac
  development report. The new visual-intent keyword router has NOT
  demonstrated a measured improvement on this set.

## Provisional test metrics (18 queries)

| Mode | All Recall@5 | All Hit@5 | All MRR@5 |
| --- | ---: | ---: | ---: |
| Visual | 0.3925 | 0.6667 | 0.4676 |
| Transcript | 0.4159 | 0.5000 | 0.4167 |
| Hybrid | **0.5224** | **0.7222** | **0.5759** |

Test breakdown by the query's proposed modality:

| Query type (count) | Visual Recall | Transcript Recall | Hybrid Recall | Hybrid MRR |
| --- | ---: | ---: | ---: | ---: |
| Visual (7) | 0.5347 | 0.0694 | 0.4776 | 0.5476 |
| Speech (5) | 0.2500 | 1.0000 | 0.7833 | 0.8667 |
| Mixed (6) | 0.3452 | 0.3333 | 0.3571 | 0.3667 |

The Hybrid top five contained at least one candidate relevant window in
13 of 18 queries (Hit@5 = 0.7222). The five zero-hit queries were
`q09`, `q10`, `q14`, `q21` and `q24`.

## Confirmed retrieval mismatches, not proven root causes

| Query | Evidence-derived observation | Further diagnosis needed |
| --- | --- | --- |
| q09 (mixed, interview) | Transcript-only reached both candidate relevant windows (Recall@5 1.0), while hybrid reached neither (0.0) | Investigate fusion weighting and visual embedding rank; do not tune the old test split |
| q10 (visual, interview) | Hybrid top result was NASA rather than the relevant interview segment; no labeled hit | Appearance ambiguity and original labels need visual review |
| q14 (visual, film) | Hybrid top five were NASA scenes; no labeled Tears of Steel window was returned | Cross-video visual similarity, prompt specificity and sampling |
| q21 (mixed, NASA) | Hybrid returned NASA windows but none of seven labeled instrument-panel target windows; visual-only covered 3/7 | Time-localization vs dialogue/text fusion; label exhaustiveness |
| q24 (mixed, NASA) | Hybrid top five contained no two labeled astronaut/backdrop windows | Speaker/background identity and ASR/visual localization |

Other hard-to-interpret issues:

- Multiple queries label more than 5 relevant windows (dev q02, test q07, q16, q21); exact Recall@5 cannot reach 1.0 on those queries.
- All errors are *mismatches against weak candidate labels*, not necessarily model mistakes: an unlabelled but semantically relevant scene can appear as a false positive.
- Transcript-only speech query recall of 1.0 on 5 test prompts is limited to the supplied AI-assisted labels and cannot establish external performance.
- The evaluation code reports macro means across queries and RRF results based on complete FAISS rankings, but the archived `per_query.json` includes only the top 5 predictions.

## Phase acceptance status

| Gate | Status | Evidence / limitation |
| --- | --- | --- |
| Three-video index and metadata | **PASS** | Hash and reference audit |
| CLIP/MiniLM retrieval execution on Mac MPS | **PASS** | 6 dev + 18 test run |
| All dev/test report arithmetic | **PASS** | Independently recomputed from ZIP |
| Report ZIP reproducibility | **PASS** | ZIP archive and separate files matched |
| Independent human visual/audio label verification | **NOT VERIFIED** | AI-assisted contact-sheet and ASR source |
| Safari playback across all three videos | **NOT VERIFIED** | Earlier screenshot covered NASA, not the full matrix |
| Public hosted multi-user security | **OUT OF SCOPE** | Local-only prototype |

## Portfolio wording

Recommended: *Designed and implemented a local multimodal video scene search
prototype with timestamped playback using Whisper, CLIP, MiniLM, FAISS and
intent-weighted RRF; ran a reproducible exploratory 24-query evaluation and
audited source/index integrity.*

Do NOT write a resume line claiming independently verified Recall@5 = 52.24%
or a validated production-grade system. If quoting the numerical metrics in
a technical report, always label them **AI-assisted weak-label evaluation**.

## Remaining steps outside the GitHub-only workflow

1. For a true scientific retrieval benchmark, obtain an independent reviewer
   to check ground truth against source audio/video, and freeze fresh held-out
   evaluation queries before further model tuning.
2. Use Streamlit locally on the Mac and verify playback + timestamp selection
   at least once in each of the three source videos.
3. Record a short attributed demo screen capture; do not redistribute
   original video/music without checking the exact source permissions.
4. Public hosting would separately require authentication, media isolation,
   quotas, retention/privacy policies and threat-model acceptance.

Source of this report: owner-supplied `input-manifest.json`,
`RELEASE_STATUS.json`, `RELEASE_SUMMARY.md` and
`shareable-release-evidence.zip` from the Mac run of 27 October 2026.
Only derived numeric findings are published here; no media or transcript
content is copied into GitHub.
