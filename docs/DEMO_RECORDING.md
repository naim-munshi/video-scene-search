# 80-second portfolio demo — script and publication rules

**This is a storyboard, not a claim that a screen recording already exists.**
The app and original media are on the owner's Mac. No video content is
available to the GitHub CI runner or the chat's GitHub connector.

## Reuse genuine screenshots (not synthetic mockups)

The owner's 27 October 2026 Streamlit captures contain three usable portfolio
screens: **overview dashboard**, **three-video library**, and **NASA Apollo 15
hybrid search with real timestamp playback**. Prefer these factual screenshots
over AI-generated images or unreviewed contact sheets. A separate ready-to-copy
`video_scene_search_demo_gallery.zip` bundle has been prepared from the
owner-provided screenshots. It contains:
- `docs/assets/demo/01-overview.jpg` (3 videos, 252 windows, query modes)
- `docs/assets/demo/02-video-library.jpg` (source-attributed collection cards)
- `docs/assets/demo/03-timestamp-search.jpg` (NASA 01:50 matching moment)
- `docs/DEMO_GALLERY.md` (captions, source credits, weak-label caveat)

These **binary images are not yet committed to GitHub**. The first
`unzip` attempt failed because the ZIP had not been downloaded to the Mac.
Download the owner-provided ChatGPT attachment
`video_scene_search_demo_gallery.zip` to `~/Downloads` first. Then run:

```bash
cd ~/video-scene-search
git pull --ff-only origin main
python scripts/install_demo_gallery.py ~/Downloads/video_scene_search_demo_gallery.zip
git add docs/DEMO_GALLERY.md docs/assets/demo
git commit -m "docs(demo): add original Streamlit screenshots with attribution"
git push origin main
git tag -a v0.1.0 -m "Video Scene Search v0.1.0 local portfolio"
git push origin v0.1.0
```

The installer checks the exact ZIP and each original screenshot SHA-256
before writing anything; it cannot work until the file is actually saved
to the Mac. After the gallery commit, pushing `v0.1.0` triggers
`.github/workflows/publish-release.yml`: it reruns unit tests, verifies
image hashes, and creates a GitHub Release with notes and a demo screenshot
ZIP. If that GitHub Action fails, **do not claim a published release**.
No original videos, model weights, transcripts, raw contact sheets or
FAISS indexes are uploaded.

Do not claim a screenshot proves independently verified retrieval accuracy.
Gallery attributions credit ConversationEDU, Blender Foundation and NASA /
Apollo 15 Learning Hub.

## Record locally

1. From `~/video-scene-search`, activate `.venv` and run
   `SCENE_INDEX=artifacts/portfolio-real-v2 python -m streamlit run app.py --server.address 127.0.0.1`.
2. Open `http://127.0.0.1:8501` in Safari. In the sidebar select
   `portfolio-real-v2` and confirm that three sources are listed.
3. Use macOS Screenshot > Record Selected Portion (Cmd-Shift-5).
   Keep personal notifications, usernames, local paths and other private
   tabs out of frame. Voice narration is optional.
4. Search for timestamped results as below. Confirm actual playback
   is relevant on screen before narrating it as a success.

## Shot list (target 75–90 seconds)

| Approx. time | Scene | What to show |
| --- | --- | --- |
| 0–10s | Home | Three indexed real videos, 252 searchable windows, search box |
| 10–30s | Speech query | Search `A narrator introduces Apollo 15 as an upcoming twelve-day mission.` in Transcript; open result and play from the ranked timestamp |
| 30–50s | Visual query | Search `A man uses bright pink and green holographic displays in a laboratory.` in Visual; show thumbnail, chosen video and timestamp |
| 50–65s | Hybrid | Search `Two people talk beside a canal railing about robotics and a robotic hand.` in Hybrid; explain multimodal RRF |
| 65–80s | Evidence and caveat | Show metric report summary with explicit `AI-assisted weak-label exploratory` warning; do not claim independently verified accuracy |

Tip: Keep real search results visible so viewers know this is working
software, not a pre-rendered mockup. Do not imply an exact scene appears
unless you have just verified that result from the actual clip.

## Rights and consent

- Source-page licensing does not automatically grant permission to publish
  every face, audio/music component, trademark or third-party footage.
- The README records original source URLs and attribution. Confirm the
  exact license and required credit for any redistributed excerpt.
- NASA archival, Blender and interview material need separate attribution
  checks before uploading a montage or audio to public platforms.
- If reuse conditions are uncertain, record app chrome/results using your
  own recreated test media instead, and do not claim it is one of the
  underlying three archived works.

## Final acceptance: what may be claimed

Code compile/test CI PASS and Mac local engineering release PASS are
documented. The separate `media_playback_preflight.py` verifies local
H.264/AAC streams and decodes frames/audio at three points per video.
That is NOT Safari acceptance. The Video Library offers three playback
checkpoints per video; only the operator can confirm seeing and hearing
all nine and export a `USER_SELF_ATTESTED` JSON.

The 24-query results are weak-label measurements; quote numbers only
with that qualification. Independent human-reviewed accuracy remains
unverified. Never imply the optional demo has been recorded until
it actually exists.
