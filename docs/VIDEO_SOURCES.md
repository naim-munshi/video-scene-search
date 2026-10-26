# Three externally sourced evaluation videos (source catalogue)

These are **not stored in the GitHub repository**. Their original file
pages, license texts and durations were checked on 27 October 2026.
The one-command importer fetches public source files directly from
their archival hosts and transcodes them into H.264/AAC MP4 for
browser playback. Check the licenses and the specific footage before
publicly reusing screenshots, actors or audio excerpts.

| ID | Work | Length | License at source | Best evaluation use |
| --- | --- | --- | --- | --- |
| interview | Steve Wozniak interview (ConversationEDU) | 14:48 | CC BY 3.0 | Interview speech, discussions and talking-head retrieval |
| nasa | NASA Aeronautics and Space Report / Apollo 15 | 14:47 | Public domain per Apollo 15 Learning Hub | Narration, astronaut interviews and documentary/archival imagery |
| film | Blender Foundation Tears of Steel | 12:14 | CC BY 3.0 | Spoken dialogue and scene changes in live action/CGI |

Original source / license listings:
- https://commons.wikimedia.org/wiki/File:Interview_with_Steve_Wozniak.webm
- https://apollo15hub.org/items/show/176
- https://commons.wikimedia.org/wiki/File:Tears_of_Steel_1080p.webm
- https://creativecommons.org/licenses/by/3.0/

Required credits:
- ConversationEDU, CC BY 3.0, Wikimedia Commons source page.
- NASA, via Apollo 15 Learning Hub / Emory Center for Digital Scholarship.
- (CC) Blender Foundation | mango.blender.org. When showing the full film,
  retain its credit scroll.

## Already downloaded the two WebM files?

The user successfully downloaded `interview.webm` (160 MiB)
and `tears_of_steel.webm` (544 MiB) into `data/videos/`.
**Do not download them a second time**. Pull the latest branch and
use the source-preserving, network-disabled conversion path:

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
df -h data/videos
python scripts/prepare_portfolio_videos.py --only interview film --local-only
python scripts/real_video_preflight.py --manifest data/portfolio-corpus.json
```

The conversion saves `portfolio_interview.mp4` and `portfolio_film.mp4`
beside the original WebMs; it never deletes the manually downloaded files.
Ensure at least 1.5 GB free space before conversion. The two-video manifest
fulfils the project's 2–3 video evaluation requirement; NASA is optional.

`--local-only` guarantees no network downloading. If a source file was not
fully downloaded or cannot be decoded, repair it before indexing.

## Mac setup

```bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
python scripts/prepare_portfolio_videos.py --plan
python scripts/prepare_portfolio_videos.py
python scripts/real_video_preflight.py --manifest data/portfolio-corpus.json
scene-search ingest --manifest data/portfolio-corpus.json \
  --output artifacts/portfolio-real-v1 --whisper-model base --language en --device mps
SCENE_INDEX=artifacts/portfolio-real-v1 python -m streamlit run app.py
```

The full film source is ~545 MB before local transcoding; the interview
~160 MB. The NASA MP4 size depends on the hosting archive. Ensure free
storage, stable internet and FFmpeg. The importer downloads sequentially
and removes each original after the MP4 is created. It leaves finished
videos in `data/videos/`, plus an ignored `data/portfolio-corpus.json`
with license/source details.

To save bandwidth, start with the interview and NASA documentary only:
```bash
python scripts/prepare_portfolio_videos.py --only interview nasa
```
A generated manifest must match the selected files; to switch to all
three, use a new `--root data/portfolio-three`. Do not delete the
earlier index or existing human labels.

## Accuracy and rights caveats

The user-provided synthetic development score of 100% hybrid Recall@5
comes from six deterministic synthetic queries. This new external
corpus is a different dataset, not yet ingested, labeled or evaluated;
do not transfer the synthetic metric to these clips.

The labels `rights_confirmed: true` encode the source pages' published
reuse permissions, not a guarantee that every visible face, archival
insert or music component can be separately republished or used in ads.
Do not put the downloaded media or private transcript in GitHub by
overriding `.gitignore`. Film/NASA/tech talk genres are better than three
identical cartoons, but they do not substitute for independent
real-life recording under your control.

## If a host blocks the downloader

Use the source-page link to download the corresponding file in a browser.
Convert a downloaded file with FFmpeg and place it in `data/videos/`
under the expected MP4 name; the importer verifies existing files
using ffprobe before building the manifest. Host availability is
external and was not verified from the user's Mac.
