"""Export compact, human/assistant-reviewable evidence for ALL video windows.

Runs OFFLINE. No ASR, vision-model download or video decoding: reuses the
completed index's sampled JPEG frames and timestamp-aligned transcripts.
The resulting ZIP can be inspected in chat to assist *candidate* annotations,
but model-assisted labels are NOT independent human-verified ground truth.

Usage:
  python scripts/export_annotation_evidence.py
  python scripts/export_annotation_evidence.py --index artifacts/portfolio-real-v2 \
    --output reports/portfolio-real-v2-evidence.zip
"""
import argparse
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scene_search.core import read_json, sha256
from scene_search.ui_helpers import readable_time
from scripts.seed_portfolio_queries import QUERIES

COLUMNS = 4
ROWS = 5
CARD_WIDTH = 400
CARD_HEIGHT = 151
THUMB_WIDTH = 184
THUMB_HEIGHT = 104
SHEET_MARGIN = 13
STOPWORDS = frozenset(
    "a an the and or to in on with of is are was were while about at by this "
    "there their for from someone person people one two video scene footage "
    "appears shown shows visible someone some man woman during".split()
)


def make_queries(index, queries_path=None):
    """Never confuse suggested query text with reviewed annotations."""
    digest = sha256(index / "build.json")
    if queries_path is not None:
        source = Path(queries_path).expanduser().resolve()
        obj = read_json(source)
        if obj.get("build_sha256") != digest:
            raise ValueError("Query file belongs to a different video index")
        rows = obj.get("queries", [])
        if len(rows) != 24 or any(not q.get("text", "").strip() for q in rows):
            raise ValueError("Query file must contain 24 nonempty query texts")
        text_by_id = {q["id"]: q for q in rows}
        if len(text_by_id) != 24:
            raise ValueError("Query IDs must be unique")
    else:
        text_by_id = {}
    result = []
    for i, (qid, video_id, suggested, kind) in enumerate(QUERIES):
        selected = text_by_id.get(qid)
        result.append({
            "id": qid,
            "video_id": video_id,
            "text": selected["text"] if selected else suggested,
            "kind": selected["kind"] if selected else kind,
            "split": "dev" if i < 6 else "test",
            "relevant": [],  # No fabricated accuracy labels or predictions.
            "review_status": "candidate_only",
        })
    return {"build_sha256": digest, "status": "unverified_model_assisted",
            "queries": result}


def read_index(index):
    """Read metadata with SHA-256 integrity checks, without native FAISS."""
    index = Path(index).expanduser().resolve()
    meta = read_json(index / "build.json")
    required = ["corpus.json", "windows.json", "frames.json", "segments.json"]
    manifest = meta.get("files", {})
    if meta.get("schema_version") != 1 or any(k not in manifest for k in required):
        raise ValueError("Incomplete or unsupported search index")
    for name in required:
        path = (index / name).resolve()
        if not path.is_relative_to(index) or sha256(path) != manifest[name]:
            raise ValueError(f"Index metadata integrity failed: {name}")
    videos = read_json(index / "corpus.json")["videos"]
    windows = read_json(index / "windows.json")
    frames = read_json(index / "frames.json")
    segments = read_json(index / "segments.json")
    allowed = {v["id"] for v in videos}
    if allowed != {r[1] for r in QUERIES}:
        raise ValueError("Expected the three-video portfolio index")
    if not windows or len({w["id"] for w in windows}) != len(windows):
        raise ValueError("Missing or duplicate index windows")
    return index, videos, windows, frames, segments


def token_overlap(query, passage):
    """Weak lexical hint for navigating ASR, NEVER a relevant-window label."""
    terms = {t for t in re.findall(r"[a-z]{3,}", query.casefold())
             if t not in STOPWORDS}
    tokens = {t for t in re.findall(r"[a-z]{3,}", passage.casefold())
              if t not in STOPWORDS}
    return sorted(terms & tokens)


def build_evidence(index, queries_path=None):
    index, videos, windows, frames, segments = read_index(index)
    queries = make_queries(index, queries_path)
    win_ids = {w["id"] for w in windows}
    frame_map, speech_map = defaultdict(list), defaultdict(list)
    for frame in frames:
        for wid in frame["window_ids"]:
            if wid not in win_ids:
                raise ValueError(f"Invalid frame window reference: {wid}")
            candidate = (index / frame["file"]).resolve()
            if not candidate.is_relative_to(index) or not candidate.is_file():
                raise ValueError(f"Missing/unsafe video preview image: {frame['file']}")
            frame_map[wid].append({
                "path": str(candidate),
                "timestamp": float(frame["timestamp"]),
            })
    for segment in segments:
        for wid in segment["window_ids"]:
            if wid not in win_ids:
                raise ValueError(f"Invalid speech window reference: {wid}")
            speech_map[wid].append({
                "start": round(float(segment["start"]), 2),
                "end": round(float(segment["end"]), 2),
                "text": segment["text"],
            })
    records = []
    for window in windows:
        wid = window["id"]
        passages = sorted(speech_map.get(wid, []),
                         key=lambda s: (s["start"], s["end"]))
        record = {
            "id": wid,
            "video_id": window["video_id"],
            "start": window["start"],
            "end": window["end"],
            "time": readable_time(window["start"]) + "–" +
                    readable_time(window["end"]),
            "transcripts": passages,
            "transcript_text": " ".join(s["text"] for s in passages),
            "frames_available": len(frame_map[wid]),
        }
        records.append(record)
    hints = []
    for q in queries["queries"]:
        candidates = []
        for record in records:
            if record["video_id"] != q["video_id"]:
                continue
            matches = token_overlap(q["text"], record["transcript_text"])
            if matches:
                candidates.append({
                    "window_id": record["id"],
                    "time": record["time"],
                    "matched_words": matches,
                    "asr_excerpt": record["transcript_text"][:400],
                })
        candidates.sort(key=lambda row: (-len(row["matched_words"]),
                                         row["window_id"]))
        hints.append({
            "query_id": q["id"],
            "target_video": q["video_id"],
            "query_type": q["kind"],
            "weak_transcript_keyword_hints": candidates[:12],
            "notice": "Keyword hints from ASR only; visual matches require image review.",
        })
    return {
        "root": index, "videos": videos, "windows": windows,
        "frame_map": frame_map, "records": records,
        "queries": queries, "keyword_hints": hints,
    }


def font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def choose_two_images(images):
    ordered = sorted(images, key=lambda f: f["timestamp"])
    if not ordered:
        return []
    if len(ordered) == 1:
        return [ordered[0]]
    return [
        ordered[min(len(ordered) - 1, int(len(ordered) * .25))],
        ordered[min(len(ordered) - 1, int(len(ordered) * .75))],
    ]


def render_page(title, rows, frame_map):
    """Render up to 20 windows, two indexed frames for each window."""
    from PIL import Image, ImageDraw
    if not 1 <= len(rows) <= COLUMNS * ROWS:
        raise ValueError("Invalid contact sheet page size")
    canvas = Image.new("RGB", (
        COLUMNS * CARD_WIDTH + SHEET_MARGIN * 2,
        ROWS * CARD_HEIGHT + 68,
    ), "#F0F4F8")
    draw = ImageDraw.Draw(canvas)
    draw.text((17, 15), title, font=font(21), fill="#133A44")
    for i, row in enumerate(rows):
        col, line = i % COLUMNS, i // COLUMNS
        x = SHEET_MARGIN + col * CARD_WIDTH
        y = 56 + line * CARD_HEIGHT
        draw.rounded_rectangle(
            (x + 4, y + 3, x + CARD_WIDTH - 6, y + CARD_HEIGHT - 8),
            radius=7, fill="#FFFFFF", outline="#D8E4EB", width=1,
        )
        draw.text((x + 14, y + 10),
                  f"{row['id']}  ·  {row['time']}",
                  fill="#0C4250", font=font(16))
        two = choose_two_images(frame_map[row["id"]])
        if not two:
            draw.text((x + 14, y + 53), "NO INDEXED IMAGE",
                      fill="#A13030", font=font(15))
        for j, record in enumerate(two):
            path = Path(record["path"])
            with Image.open(path) as im:
                image = im.convert("RGB")
                image.thumbnail((THUMB_WIDTH, THUMB_HEIGHT),
                                resample=Image.Resampling.LANCZOS)
            origin_x = x + 14 + j * (THUMB_WIDTH + 10)
            origin_y = y + 37
            draw.rectangle((origin_x, origin_y,
                            origin_x + THUMB_WIDTH, origin_y + THUMB_HEIGHT),
                           fill="#DCE7EB")
            canvas.paste(image, (
                origin_x + (THUMB_WIDTH - image.width) // 2,
                origin_y + (THUMB_HEIGHT - image.height) // 2,
            ))
    stream = io.BytesIO()
    canvas.save(stream, "JPEG", quality=76, optimize=True)
    return stream.getvalue()


def export_evidence(index, output, queries_path=None):
    """Save compact ZIP atomically; never overwrite a previous evidence pack."""
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError(f"Output exists; choose a fresh ZIP path: {output}")
    item = build_evidence(index, queries_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pages = []
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".evidence-", suffix=".tmp",
            dir=output.parent, delete=False
        ) as handle:
            tmp_path = Path(handle.name)
        with zipfile.ZipFile(tmp_path, mode="w",
                             compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6) as archive:
            def store_json(name, payload):
                archive.writestr(
                    name, json.dumps(payload, ensure_ascii=False,
                                     indent=2) + "\n")
            store_json("queries.json", item["queries"])
            store_json("windows_and_transcripts.json", item["records"])
            store_json("keyword_hints_NOT_ground_truth.json",
                       item["keyword_hints"])
            for video in item["videos"]:
                group = [w for w in item["records"]
                         if w["video_id"] == video["id"]]
                for start in range(0, len(group), COLUMNS * ROWS):
                    number = start // (COLUMNS * ROWS) + 1
                    file = f"contact_sheets/{video['id']}-{number:02d}.jpg"
                    label = (f"{video['title']}  ·  page {number}  ·  "
                             f"{group[start]['time']} onward")
                    archive.writestr(
                        file, render_page(label, group[start:start + 20],
                                          item["frame_map"]),
                        compress_type=zipfile.ZIP_STORED)
                    pages.append(file)
            archive.writestr("READ_ME_FIRST.txt",
                "Video Scene Search — independent evidence review package\n\n"
                "Includes 2 sampled frames for each ten-second indexed window,\n"
                "window timestamps, ASR transcript passages and 24 query prompts.\n"
                "No original MP4/WebM or private FAISS indexes are included.\n"
                "Matched keyword hints are navigation aids, NOT evidence of\n"
                "relevance and NOT independent retrieval ground truth.\n\n"
                "For assistant-assisted labeling, upload this ZIP in chat.\n"
                "The reviewer should inspect ALL pertinent contact sheets\n"
                "and ASR text, report uncertain/no-match queries honestly,\n"
                "and preserve split separation. Automatic/assistant labels\n"
                "must be called weak or model-assisted, never human-verified.\n")
        if output.exists():
            raise ValueError(f"Output appeared during export: {output}")
        os.replace(tmp_path, output)
        return {"output": str(output),
                "video_count": len(item["videos"]),
                "window_count": len(item["records"]),
                "contact_sheets": len(pages),
                "candidate_queries": len(item["queries"]["queries"]),
                "zip_size_mib": round(output.stat().st_size / (1024 * 1024), 2),
                "label_status": "UNVERIFIED_ASSISTANT_REVIEW",
                "note": "Upload ZIP to ChatGPT for visual + transcript evidence review; "
                        "not an independent accuracy benchmark."}
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="artifacts/portfolio-real-v2")
    parser.add_argument("--output", default="reports/portfolio-real-v2-evidence.zip")
    parser.add_argument("--queries", default=None,
                        help="Optional 24-query draft; otherwise uses seeded suggestions")
    args = parser.parse_args()
    try:
        print(json.dumps(export_evidence(args.index, args.output, args.queries),
                         ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        parser.exit(2, f"Evidence export failed: {exc}\n")


if __name__ == "__main__":
    main()
