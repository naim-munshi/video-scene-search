# Video Scene Search

A local Python proof of concept that retrieves timestamped video windows using
visual similarity, transcript similarity, and reciprocal rank fusion (RRF).
Built as an AI engineering portfolio project for media retrieval and analysis
of false positives and missed relevant scenes. It is not affiliated with ABEMA.

## Status

Implementation includes ingestion, FAISS indexes, three retrieval modes, a
Streamlit playback/annotation interface, and reproducible evaluation reports.
No real-corpus retrieval quality is claimed yet. Supply permission-cleared videos
and manually label queries before reporting Recall@5. No paid API is required.

| Method | Recall@5 | Hit@5 | MRR@5 |
| --- | --- | --- | --- |
| Visual-only | Not measured | Not measured | Not measured |
| Transcript-only | Not measured | Not measured | Not measured |
| Hybrid | Not measured | Not measured | Not measured |

## Start with a synthetic demo (no private videos needed)

The repository also includes a **three-video, spoken-audio synthetic demo**
with deterministic labels and a reproducible evaluation workflow. This is an
engineering smoke/illustration only, not a real-scene quality result. Once the
project is installed, run:

```bash
python scripts/synthetic_demo.py generate
scene-search ingest --manifest data/demo-corpus.json --output artifacts/demo-index --whisper-model tiny --language en
python scripts/synthetic_demo.py labels --index artifacts/demo-index
scene-search evaluate --index artifacts/demo-index --labels evaluation/demo-labels.json --split test --output reports/demo-test
SCENE_INDEX=artifacts/demo-index python -m streamlit run app.py --server.address 127.0.0.1
```

The generator needs FFmpeg. It uses FFmpeg's `flite` filter when available; on macOS, it otherwise falls back to the built-in `say` command for speech. See
[Demo & acceptance](docs/DEMO_AND_ACCEPTANCE.md) for setup, preflight checks
for 2–3 real talking videos, controlled test labels, evaluation, and screen
recording criteria. Real-scene Recall@5/MRR remains unmeasured without those
actual videos and human-reviewed labels.

## Setup on Mac or Linux

Use Python 3.12 (3.10–3.13 supported by this project's declared range).
If your default Python is 3.14, install 3.12 separately; do not change your other projects.
From the extracted `video-scene-search` folder:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m unittest discover -s tests -v
```

The first ingest/search downloads pretrained weights from Hugging Face.
Dependencies and weights can consume several GB; initial CPU processing can be slow.
Dependencies have compatibility ranges, not a universal platform lockfile.
PyAV is constrained below 16: the real-model smoke test exposed an audio-decoding
API incompatibility between faster-whisper 1.2.1 and PyAV 19.0.2.
Each index records the actual package versions; save `python -m pip freeze` with
your completed experiment. Model repository revisions are not pinned in v0.1;
archive the model cache for strict future reproduction.


### Apple Silicon: CLIP native crash isolation

If the ingest process previously ended with a segmentation fault inside
`torch.nn.Conv2d` / `CLIPModel`, pull the latest commit. On macOS the
visual image encoder now runs in a separate Python process, with
`OMP_NUM_THREADS=1` and a small batch size (2), to separate PyTorch
convolution from native audio/video libraries. This is a mitigation,
**not evidence that the Mac crash is fixed**.

First verify GPU availability:

```bash
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

When MPS is available, try:

```bash
python -X faulthandler -m scene_search.cli ingest --manifest data/demo-corpus.json --output artifacts/demo-index-mps --whisper-model tiny --language en --device mps
```

If MPS is unavailable, use `--device cpu` with the same command and a fresh
output directory. A native failure from the visual subprocess now reports a
non-zero exit rather than claiming a completed index. Do not try searching
until an index contains `build.json`. For explicit diagnosis, flags
`--embedding-mode in-process` and `--visual-batch-size 1` are available.

## 1. Add videos

Start with one self-recorded video, then expand to 2–3 videos of 10–20 minutes.
Prefer constant-frame-rate MP4/H.264 with AAC audio for browser playback.
Place videos in `data/videos/`, then edit `examples/corpus.json`:

- Set `path` relative to the manifest file, not your terminal directory.
- Use unique IDs such as `video_01`, `video_02`.
- Record source, license and attribution; set `rights_confirmed` to true only
  after checking ownership/permission and participant consent where applicable.
- For Creative Commons content, record the exact source URL, license/version,
  creator and attribution. Do not assume a publicly accessible video is reusable.

No third-party video is bundled. Private media, transcripts, frames and indexes
remain local and are excluded from git. Do not publish them without permission.

## 2. Build

```bash
scene-search ingest --manifest examples/corpus.json --output artifacts/index
```

This runs faster-whisper `base` on CPU/int8, extracts frames every 2 seconds,
encodes frames with CLIP ViT-B/32 and transcript segments with multilingual
MiniLM, and writes two normalized inner-product FAISS indexes. Ten-second
windows form the shared result and ground-truth unit.

On Apple Silicon, `--device mps` optionally accelerates embeddings. Whisper
continues on CPU because CTranslate2 does not use MPS. CPU is the default.
Use `--language ja` or `--language en` if automatic language detection is wrong.
Use a larger `--whisper-model small` only after measuring transcription quality.

Output directories cannot be overwritten. Rebuild into `artifacts/index-v2`
when changing the corpus/configuration; annotations are tied to the build hash.
Atomic publication prevents an interrupted build from appearing complete.

## 3. Search and play

```bash
scene-search search "Two people talking at a table" --mode visual
scene-search search "Someone discusses a project deadline" --mode transcript
scene-search search "A person explains something while using a laptop" --mode hybrid
python -m streamlit run app.py
```

Open `http://127.0.0.1:8501`. Choose a result to start playback at its window.
For a different index:

```bash
SCENE_INDEX=artifacts/index-v2 python -m streamlit run app.py
```

Use English for visual and hybrid queries. Multilingual transcript embeddings
are included, but Bengali/Japanese retrieval quality is not established.
CLIP has a short token limit; keep visual queries concise.

Visual scoring is the maximum frame cosine similarity in a window. Transcript
scoring is the maximum cosine similarity among segments overlapping a window.
Each window occurs once per ranking. Hybrid uses full-list RRF with constant 60,
not a sum of incompatible cosine scores. All candidates are scanned for this
small corpus. A speech-free window is absent from transcript ranking. If all
speech is absent, transcript returns no results and hybrid follows visual rank.
There is no confidence threshold; top results may all be irrelevant.

## 4. Annotate and evaluate

```bash
scene-search init-labels --index artifacts/index --output evaluation/labels.json
```

1. Use the **Annotate before evaluating** tab to watch source windows, without
   consulting ranked search results.
2. Load the draft labels file. Fill its 24 queries: 8 visual, 8 speech, 8 mixed.
   Replace any query that has no relevant moment in this corpus.
3. Hand-label every relevant window ID, such as `video_01:00012` (120–130s).
   Label windows containing visible/audible evidence sufficient to answer the
   query; label both sides of a boundary if both independently qualify.
4. Keep 6 development queries and 18 held-out test queries. Do not copy queries
   between splits. Choose parameters on dev, freeze them, and run test once.
5. Mark the annotations complete and download `labels.json`. Put it in
   `evaluation/labels.json`. Session edits are not saved until downloaded.

```bash
scene-search evaluate --labels evaluation/labels.json --split dev --output reports/dev-v1
scene-search evaluate --labels evaluation/labels.json --split test --output reports/test-v1
```

The evaluator rejects draft annotations, empty relevance sets, unknown window
IDs, duplicate queries, stale build hashes and existing report directories.
Reports include overall/per-type CSV metrics, per-query false positives and
misses, a Markdown comparison, and an evidence manifest with build/label hashes.

- **Recall@5:** relevant windows retrieved / all manually relevant windows,
  averaged across queries. Queries with more than five relevant windows cannot
  reach 1.0 at k=5; document this instead of silently reducing the denominator.
- **Hit@5:** fraction of queries with any correct window in the first five.
- **MRR@5:** mean reciprocal rank of the first correct result (zero if absent).

Matching uses exact fixed-window IDs. These metrics are **window retrieval**
metrics, not automatically true semantic-scene recall. Adjacent windows are
distinct units. Annotation errors and unlabelled positives bias the evaluation;
have another person review a subset where possible. The small shared-video
test set supports a corpus-specific comparison, not generalization claims.

## 5. Analyze failures and finish the portfolio

Fill the human diagnosis fields in the generated `report.md`; do not label a
suspected cause as proven. Review 3–5 failures with screenshots/timestamps you
are permitted to publish. Candidate causes to check:

| Observation | Possible cause to verify |
| --- | --- |
| A short action is missed | Two-second sampling skipped it |
| A similar-looking scene is returned | CLIP captures appearance, not precise action/time |
| The topic is missed in transcript search | ASR error or embedding mismatch |
| Hybrid ranks a correct result lower | An irrelevant modality outranks useful evidence |

Copy measured test results into the table above, record corpus/license details,
dependency versions and hardware, and add a short demo recording.
Do not claim improvements unless the measured comparison supports them.

CV wording after implementation verification, without invented numbers:

> 動画シーン検索PoCを開発。Whisper・CLIP・FAISSを用い、映像・音声文字起こし・統合検索を実装。

After manually labelled evaluation, add the actual query count and Recall@5
comparison. See `docs/VALIDATION.md` for what was checked during this build.

## Software checks

```bash
python -m unittest discover -s tests -v
RUN_INTEGRATION=1 python -m unittest discover -s tests -v
python scripts/real_model_smoke.py
```

The integration suite uses real PyAV/FAISS and Streamlit AppTest with fake
encoders/ASR so it runs without model downloads. The final smoke script uses
real CLIP, multilingual MiniLM and Whisper tiny on generated video/speech;
it requires `ffmpeg` with the `flite` filter. Neither check measures real-world
retrieval quality. Normal ingestion does not require that ffmpeg executable.

## Limitations and local security

- v0.1 uses fixed windows, not shot-boundary detection or a temporal video model.
- Sampling uses video presentation timestamps; variable-frame-rate sources should be converted
  to constant FPS before ingestion. Video codec metadata may be imperfect.
- The local app has no user authentication and is bound to loopback. Do not
  expose it publicly; it can display the private corpus.
- Load only locally generated, trusted FAISS artifacts. Hash checks detect
  accidental corruption, not malicious replacement of both files and hashes.
- Models run locally after download. Model downloads contact external hosts.
  No paid cloud inference, automatic uploads, or third-party media download occurs.
- Build metadata includes original absolute media paths; redact before publication.

## References

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [Sentence Transformers image search](https://sbert.net/examples/sentence_transformer/applications/image-search/README.html)
- [FAISS](https://github.com/facebookresearch/faiss)
- [Streamlit video playback](https://docs.streamlit.io/develop/api-reference/media/st.video)
