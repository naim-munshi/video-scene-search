# Security policy

## Supported scope

| Scope | Support status |
| --- | --- |
| `main` — local single-user prototype | Best-effort security fixes |
| `MdNaim` — historical development branch | Legacy; report issues against `main` |
| Public hosted / multi-tenant deployments | **Not supported** |

This repository is a locally run research prototype, **not a hardened production service**. Do not expose Streamlit port 8501 or 8502 to untrusted networks, configure a public tunnel, or store third-party sensitive video data in a shared environment without a separate security design.

## Reporting a vulnerability

For confidential security concerns, use GitHub's **Report a vulnerability** / private vulnerability reporting feature **if enabled** on this repository. If that feature is unavailable, contact the maintainer privately through a published profile contact channel; do not submit sensitive exploit details to a public issue. Never post credentials, private media, source paths containing personal information or model caches.

For non-sensitive bugs, open a public issue with reproduction steps, platform, expected/actual outcome and redacted logs.

## Security boundaries

- Source videos, transcripts, embeddings, reports and labels are intentionally excluded from version control.
- The Streamlit interface binds to `127.0.0.1`, enables XSRF protection and is intended for a trusted local operator.
- Imported media is not a validated trust boundary; passing `ffprobe` or FFmpeg spot decoding does **not** make arbitrary files safe or establish redistribution rights.
- FAISS data should be loaded only from a trusted local build. SHA-256 file hashes detect unintended changes, but are not cryptographic signatures authenticating a publisher.
- Dependencies and Hugging Face model revisions are not fully pinned; reproducibility and software-supply-chain provenance require additional work.
- **No** authentication, multi-user isolation, per-tenant privacy, public upload scanning, deletion guarantees, rate limits or hosted threat model is implemented.

## Incident response

If a private video or secret is committed, remove access promptly, rotate affected secrets, investigate history and follow GitHub's documented guidance for sensitive-data removal. A new commit deleting a file does not automatically erase it from Git history.

The extended security review is in [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md).
