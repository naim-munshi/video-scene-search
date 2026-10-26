# Security and privacy review — video-scene-search

## Threat model and intended deployment

This is a **single-user local research prototype**, not a public multi-tenant
video search service. The Streamlit server listens on `127.0.0.1` (loopback).
It stores source media, frames, transcripts, FAISS indexes, annotation files
and evaluation reports on the user's Mac, ignored by Git. No login or
remote-tenant authorization model exists. Do **not** expose port 8501 to
untrusted networks or add a public upload endpoint without separate design.

## Checks and controls

| Area | Protection / observation | Remaining limitation |
|---|---|---|
| Source rights | Manifest demands explicit `rights_confirmed: true` and provenance | Claim is self-attested; verify permission/consent manually |
| Private files | `data/`, `artifacts/`, `evaluation/`, `reports/` ignored by Git | A manual `git add -f` or copied file can still leak data |
| Integrity | Build stores SHA-256 hashes of every generated index file; search verifies before native FAISS read | If an attacker can replace both manifest and FAISS bytes, hashes are not a digital signature |
| Native crash | Mac visual embedding and search query workers run in subprocesses | Worker itself may crash; PyTorch/FFmpeg are native dependencies |
| Command injection | Subprocess calls use argument vectors, not shell interpolation; search queries pass via local JSON | Only use locally trusted video/media files |
| Search/annotation | Query length restricted to 500 characters; labels check duplicates and build hash | No cross-user permission management; this is offline |
| Video limits | Real-video preflight checks duration, stream presence, and codec | It is advisory; malformed large videos can exhaust memory/disk |
| External dependencies | Models downloaded from Hugging Face | Exact model revisions/weights are not pinned or signed in v0.1 |
| Remote surface | Local Streamlit server; XSRF enabled; usage stats disabled | Public reverse proxies, shared hosts, and untrusted origins are unsupported |

## Reproducible verification

```bash
python -m compileall -q src app.py scripts tests
PYTHONPATH=src python -m unittest discover -s tests -v
python scripts/acceptance_check.py --index artifacts/demo-index-isolated
```

The `acceptance_check.py` script is metadata-only by default. It does
not deserialize FAISS or download/load ML models until an optional `--query`
is supplied. This helps distinguish corrupted output from model/runtime
issues while inspecting a *trusted local* index. Its checks do not prove
retrieval accuracy or resistance to malicious input.

## Release-blocking items for a hosted/multi-user version

Implement authentication, video ownership and tenant isolation; request
and upload size limits; video sandboxing and malware/content processing;
data retention/deletion and consent policies; signed/version-pinned model
artifacts and dependency supply-chain controls; input/media quotas and
denial-of-service protections; encrypted storage where appropriate; audit
logging without leaking transcripts; network-level protection and secure
deployment reviews. None of these is needed to run the local demo but
they are **required before public service deployment**.

## Verification status

Source/static review and automated unit checks are available.
The user's Mac demonstrated successful isolated MPS ingestion and transcript/
hybrid retrieval on synthetic videos. A separate human browser playback
assessment, real-video evaluation and penetration test are **not yet done**.
