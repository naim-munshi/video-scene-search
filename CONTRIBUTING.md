# Contributing

Thanks for your interest in Video Scene Search. This repository is maintained as a **local single-user AI engineering portfolio prototype**, not a hosted service.

## Before proposing a change

- Open a GitHub issue describing the problem, expected behavior, platform, and a way to reproduce it. Do **not** attach confidential media or private transcripts.
- For retrieval improvements, describe the evaluation protocol and whether labels were independently verified. The existing 24-query set is **AI-assisted weak-labeled and already inspected**; do not use it as a new blind test.
- Keep source video permissions and attribution in mind. Do not add videos, model weights, FAISS artifacts, private labels, screenshots showing private information or generated reports to Git.

## Development setup

Python 3.12 is the known Mac configuration. Install FFmpeg and FFprobe if working with real video.

```bash
git clone https://github.com/naim-munshi/video-scene-search.git
cd video-scene-search
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m compileall -q src app.py scripts tests
python -m unittest discover -s tests -v
```

Core CI is intentionally dependency-light and does **not** prove model accuracy, macOS Metal/MPS stability, or Safari playback. Optional native end-to-end checks require FFmpeg, PyAV, FAISS and model weights; run on a suitable local machine only.

## Branch and pull-request conventions

- Target **`main`** for proposed changes.
- Work on a short-lived branch, for example `fix/video-timestamp` or `docs/evaluation`.
- Use descriptive commits, e.g. `fix(search): handle missing transcript index`.
- Include new tests or documented manual verification with changes that affect behavior.
- Keep the scope small and preserve existing media, FAISS indexes and report directories.
- Do not rewrite the historical development/test benchmark or invent performance improvements.

## Reporting results

Report dataset/source, licenses, device, model revisions where known, query count, label provenance, exact evaluation split, Recall@5/Hit@5/MRR@5 and failure cases. A candidate weak-label score is **not** an independently validated accuracy claim. New tuning should use a freshly designed held-out test set.

## Reuse and license

A code reuse license has not been specified for this project. Opening an issue or proposing a contribution does not grant extra reuse rights. If you intend to redistribute the software, please request explicit license terms from the repository owner.

See [README](README.md), [Architecture](docs/ARCHITECTURE.md), [Security](SECURITY.md) and [Project closure](docs/PROJECT_CLOSURE.md).
