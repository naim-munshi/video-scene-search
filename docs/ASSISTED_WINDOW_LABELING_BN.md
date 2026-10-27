# Annotate 24 real-video queries without watching 42 minutes

For Video Scene Search three-video portfolio index, the normal 24-label
evaluation requires all relevant 10-second windows. If you cannot watch
the original videos, this script prepares **review evidence**, which can be
shared with an assistant for model-assisted window selection.

It does **not** prove that the labels are exhaustive or independent,
and it never manufactures "human-verified" ground truth.

## One command on the user's Mac

\`\`\`bash
cd ~/video-scene-search
source .venv/bin/activate
git pull --ff-only origin MdNaim
python scripts/export_annotation_evidence.py
open -R reports/portfolio-real-v2-evidence.zip
\`\`\`

The script does not require a GPU, Whisper, CLIP, FAISS, remote API,
or additional video downloads. It only reads the completed
\`artifacts/portfolio-real-v2\` index and uses Pillow (already in the
project environment). It does not read or modify the source video files,
nor change the existing index.

Upload \`reports/portfolio-real-v2-evidence.zip\` to ChatGPT.
It includes:

- One JPEG contact sheet per approximately 20 windows, each with
  **two sampled frames**, exact window ID and time interval
- \`windows_and_transcripts.json\` — the existing 453 speech segments
  aligned to 252 windows by the original index
- \`queries.json\` — 24 candidate queries with the intended source video,
  development/test assignment and EMPTY relevance arrays
- \`keyword_hints_NOT_ground_truth.json\` — optional purely lexical
  transcript clues, not AI retrieval predictions or relevance judgments
- \`READ_ME_FIRST.txt\` — caveats about accuracy and provenance

Usually about 13 contact sheets are generated for this 252-window
index. The actual number and ZIP size are printed by the exporter.
There is no original MP4 inside the ZIP; **it still contains frame
captures and verbatim transcripts**. Inspect whether you are comfortable
sharing these excerpts before uploading. Keep it out of GitHub because
\`reports/\` is ignored by default.

## The next step in ChatGPT

Ask: "Read the attached evidence ZIP, review all contact sheets and
transcripts, and propose each q01–q24 relevant window ID. Distinguish
strongly supported windows from uncertain candidates; don't invent
unseen visual events or inaudible dialogue. Generate a draft JSON for
the same build if possible."

An assistant can inspect images and language quickly, propose
evidence-backed candidate IDs and output an \`evaluation\` JSON draft.
It is **not** equivalent to direct audio/video annotation: only two
sampled frames per 10-second window are shown, so short visual events
may be missed; faster-whisper can mis-transcribe speech; the same
source can contain many adjacent relevant windows.

Mark resulting labels as **model-assisted, unverified** unless a
human independently checks the source video/audio. Do not claim
these labels constitute independent test ground truth.

## Ground-truth versus convenience

You may use provisional labels to run a **sanity-check experiment**
as long as the report transparently says it is model-assisted
weak-label evaluation, not a measured unbiased real-world
Recall@5/MRR@5. For trustworthy portfolio claims, independently
verify relevance across windows, particularly held-out test labels.
Keep the split sealed if later conducting a proper test evaluation.

## Optional: use your edited 24-query draft

\`\`\`bash
python scripts/export_annotation_evidence.py \
  --queries evaluation/portfolio-real-v2-query-draft.json \
  --output reports/portfolio-real-v2-evidence-custom.zip
\`\`\`

The script checks \`build_sha256\`, so labels from an incompatible index
cannot be mixed. It never overwrites an existing ZIP; choose a new
\`--output\` path for another export.

## If exporting errors

First confirm \`artifacts/portfolio-real-v2/build.json\` exists and
Pillow is installed (\`python -c "from PIL import Image"\`). If your
Mac runs low on disk space, the exporter itself needs only enough
room for a small ZIP, not more ML models or duplicate videos.
