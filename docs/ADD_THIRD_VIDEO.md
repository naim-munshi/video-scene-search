# Append NASA Apollo 15 as video 3 without reprocessing the two existing videos

As of October 27, 2026, the user's Mac successfully created
artifacts/portfolio-real-v1 with exactly two videos, 163 windows,
812 CLIP frame embeddings and 291 speech segments. **Do not delete it**.
The existing two-video corpus metadata is in data/portfolio-corpus.json.

The third video is NASA Aeronautics and Space Report (Apollo 15),
approximately 14:47, listed as public domain by the Apollo 15 Learning Hub.
Original item: https://apollo15hub.org/items/show/176

## 1. Confirm NASA source is present on the Mac

The helper checks data/videos/nasa_apollo15.mp4,
data/videos/portfolio_nasa.mp4, ~/nasa_apollo15.mp4 and
~/Downloads/nasa_apollo15.mp4. If the file has another name, supply
--source "/full/path/to/the/video.mp4".

If the video isn't downloaded, and you have verified the item page and
rights, the source link previously recorded in the downloader is:

https://apollo15hub.org/files/original/6fc0646cf1fab4ba948c44826a099ed2.mp4

Download explicitly as data/videos/nasa_apollo15.mp4. Check the source
and rights independently before using it; network availability varies.

## 2. Create a NEW manifest (no copying / transcoding)

    cd ~/video-scene-search
    source .venv/bin/activate
    git pull --ff-only origin main
    python -m pip install -e .
    python scripts/add_nasa_video.py
    python scripts/real_video_preflight.py --manifest data/portfolio-corpus-3.json

This writes data/portfolio-corpus-3.json, leaving the original
data/portfolio-corpus.json untouched. It accepts externally stored
NASA files by relative path, so it requires no duplicate disk space.
Review the third video/audio/attribution before publishing any excerpt.

## 3. Append to existing complete index (not full ingest!)

    df -h data/videos

    scene-search extend \
      --base-index artifacts/portfolio-real-v1 \
      --manifest data/portfolio-corpus-3.json \
      --output artifacts/portfolio-real-v2 \
      --device mps

The append pipeline validates SHA-256 hashes of the old files and source
videos, checks original provenance, copies old thumbnails, loads the two
old FAISS indexes, then decodes, transcribes and embeds ONLY the new
NASA source. It writes a complete new index atomically. If it fails,
the old index is preserved and the new index does not appear completed.

Expect the new index to contain three videos, 163 previously indexed
windows plus the new video windows, 812 reused image vectors plus the
new frames, and 291 reused speech vectors plus the new segments.

Never run ingest into artifacts/portfolio-real-v1. Index and label IDs
belong to distinct builds; do not use old labels against the new build.
For a different third video, make a new clean manifest and distinct
index name. On a disk with little free space, the new transcript/video
processing can still exhaust storage; check df before starting.

## 4. Verify and launch

    python scripts/acceptance_check.py --index artifacts/portfolio-real-v2
    scene-search search "Apollo lunar rover" \
      --index artifacts/portfolio-real-v2 --mode hybrid --device mps
    SCENE_INDEX=artifacts/portfolio-real-v2 python -m streamlit run app.py

Results should contain all three video titles in the searchable corpus,
but a single query does not need to return a result from every source.
A working index is not a claim of search relevance.

## 5. Finish portfolio evaluation

    scene-search init-labels \
      --index artifacts/portfolio-real-v2 \
      --output evaluation/portfolio-three-labels-draft.json

Manually annotate 24 queries and freeze the dev/test split before
evaluating results. Evaluate 6 dev queries, then 18 held-out test
queries only after configuration is frozen. The previous synthetic
100% Recall@5 does NOT describe these real videos.

## Scope of testing

GitHub Actions can validate append eligibility, corruption handling
and metadata creation with lightweight tests. It cannot execute
Apple MPS/PyAV on the user's Mac or validate third-party source content.
The full incremental extension is new and must pass Mac runtime
verification before reporting it as complete.
