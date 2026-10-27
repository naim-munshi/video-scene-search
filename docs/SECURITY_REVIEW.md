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
| Video limits | Manifest input validates structure, caps entries at 200, and real-video preflight checks duration, streams and codec | The preflight is advisory; malformed/oversized videos can still exhaust resources |
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
The user's Mac has now successfully indexed three source-attributed real
videos and completed 24-query **AI-assisted weak-label** exploratory retrieval
on MPS. This is not independent accuracy validation. The new
`scripts/media_playback_preflight.py` can spot-decode video and audio via
FFmpeg, and the Streamlit Video Library can collect a nine-checkpoint
operator self-attestation. Neither has been verified against every local
video/browser session in this GitHub-only change. Public-host security testing
and a full penetration test have **not been performed**.


## New UI import surface (October 2026)

A new **local-only** MP4 importer stores each clip in a randomized folder
inside ignored data/imports/ (never overwriting existing indexes). It
requires a declared source, license, attribution, title and permission;
accepts at most 250 MiB; verifies video/audio presence and finite media
duration with ffprobe; uses a disk-space floor; and cleans up partial
files on failures. Native processing is **not triggered** on HTTP upload;
index creation needs a separate local Terminal command.

Uploaded material is still untrusted bytes, even with a valid suffix and
ffprobe metadata. This is a loopback-only personal prototype. Do **not**
expose Streamlit publicly; authentication, sandboxed media handling,
malware scanning, quotas, deletion controls and secure hosting are absent.

## v0.1 local engineering closeout

The local single-user scope is formally closed with a documented Mac
engineering release and passing CI; see `docs/PROJECT_CLOSURE.md`.
A fresh native FFmpeg decoding check is available:

```bash
python scripts/media_playback_preflight.py --index artifacts/portfolio-real-v2
```

It checks H.264/AAC presence and spot decodes real video/audio frames at
multiple timestamps; a PASS is **not** a browser/Safari security or playback
certification. Likewise, manually checked Streamlit playback is only the
operator's observation, not an independent audit. Do not expose this local
app externally or treat the unverified weak labels as reliable accuracy.
