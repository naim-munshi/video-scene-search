"""Offline video ingestion. An incomplete build is never published."""
import importlib.metadata
import math
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import make_windows, overlap, read_json, sha256, write_json

VISUAL_MODEL = "sentence-transformers/clip-ViT-B-32"
TEXT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_manifest(path):
    path = Path(path).resolve()
    data = read_json(path)
    videos = data.get("videos", [])
    if not videos:
        raise ValueError("Manifest must contain at least one video")
    ids = set()
    for v in videos:
        vid = v.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", vid) or vid in ids:
            raise ValueError("Video IDs must be unique and contain only letters, digits, _ or -")
        ids.add(vid)
        if not all(str(v.get(k, "")).strip() for k in ("title", "license", "source", "attribution")):
            raise ValueError(f"Missing provenance for {vid}")
        if v.get("rights_confirmed") is not True:
            raise ValueError(f"Confirm permission/licensing for {vid} before ingestion")
        p = (path.parent / v["path"]).resolve()
        if not p.is_file():
            raise ValueError(f"Video missing: {p}")
        v["path"] = str(p)
    return videos


def build(manifest, output, whisper_model="base", language=None, frame_seconds=2.0,
          window_seconds=10.0, device="cpu"):
    if not all(math.isfinite(x) and x > 0 for x in (frame_seconds, window_seconds)):
        raise ValueError("Sampling and window intervals must be finite and positive")
    if frame_seconds > window_seconds:
        raise ValueError("Frame interval must not exceed the window size")
    videos = load_manifest(manifest)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; use a new directory for each build")
    import cv2
    import faiss
    import numpy as np
    from PIL import Image
    from faster_whisper import WhisperModel
    from sentence_transformers import SentenceTransformer

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".scene-build-", dir=output.parent))
    try:
        (stage / "frames").mkdir()
        (stage / "transcripts").mkdir()
        # CTranslate2 uses CPU int8 on Apple Silicon; MPS is for embeddings only.
        whisper = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        visual = SentenceTransformer(VISUAL_MODEL, device=device)
        text = SentenceTransformer(TEXT_MODEL, device=device)
        windows, frame_rows, transcript_rows = [], [], []
        for v in videos:
            print(f"Processing {v['id']}: {v['title']}", flush=True)
            v["sha256"] = sha256(v["path"])
            cap = cv2.VideoCapture(v["path"])
            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if not cap.isOpened() or not math.isfinite(fps) or fps <= 0:
                    raise ValueError(f"Cannot read video: {v['id']}")
                duration = count / fps
                v["duration"] = duration
                vw = make_windows(v["id"], duration, window_seconds)
                windows.extend(vw)
                # Decode sequentially to avoid repeated keyframe seeking and timestamp drift.
                frame_number, next_sample = 0, 0.0
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    timestamp = frame_number / fps
                    if timestamp + 1e-8 >= next_sample and timestamp < duration:
                        name = f"frames/{v['id']}-{frame_number:08d}.jpg"
                        h, w = frame.shape[:2]
                        if w > 640:
                            frame = cv2.resize(frame, (640, max(1, round(h * 640 / w))))
                        if not cv2.imwrite(str(stage / name), frame):
                            raise ValueError("Could not save frame")
                        wid = vw[min(int(timestamp // window_seconds), len(vw) - 1)]["id"]
                        frame_rows.append({"video_id": v["id"], "timestamp": timestamp,
                                           "file": name, "window_ids": [wid]})
                        next_sample += frame_seconds
                    frame_number += 1
                if frame_number < count - max(2, fps):
                    raise ValueError(f"Video decoding ended early: {v['id']}")
                if not any(r["video_id"] == v["id"] for r in frame_rows):
                    raise ValueError(f"No frames extracted from {v['id']}")
            finally:
                cap.release()
            segments, info = whisper.transcribe(v["path"], language=language, vad_filter=True,
                                                condition_on_previous_text=False)
            transcript = []
            for s in segments:
                start, end = max(0, s.start), min(duration, s.end)
                if s.text.strip() and end > start:
                    row = {"video_id": v["id"], "start": start, "end": end,
                           "text": s.text.strip(), "window_ids": [w["id"] for w in vw
                           if overlap(start, end, w["start"], w["end"]) > 0]}
                    transcript.append(row)
                    transcript_rows.append(row)
            v["detected_language"] = info.language
            write_json(stage / "transcripts" / f"{v['id']}.json", transcript)
        matrix = []
        for offset in range(0, len(frame_rows), 32):
            images = []
            for row in frame_rows[offset:offset + 32]:
                with Image.open(stage / row["file"]) as im:
                    images.append(im.convert("RGB"))
            matrix.append(visual.encode(images, normalize_embeddings=True, convert_to_numpy=True))
        vectors = np.ascontiguousarray(np.concatenate(matrix), dtype="float32")
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(stage / "visual.faiss"))
        if transcript_rows:
            vectors = np.ascontiguousarray(text.encode([r["text"] for r in transcript_rows],
                batch_size=32, normalize_embeddings=True, convert_to_numpy=True), dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(stage / "transcript.faiss"))
        write_json(stage / "windows.json", windows)
        write_json(stage / "frames.json", frame_rows)
        write_json(stage / "segments.json", transcript_rows)
        write_json(stage / "corpus.json", {"videos": videos})
        packages = {p: importlib.metadata.version(p) for p in (
            "numpy", "faiss-cpu", "opencv-python-headless", "faster-whisper",
            "sentence-transformers", "torch", "transformers", "streamlit")}
        meta = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "visual_model": VISUAL_MODEL, "text_model": TEXT_MODEL,
                "whisper_model": whisper_model, "whisper_device": "cpu", "language": language,
                "frame_seconds": frame_seconds, "window_seconds": window_seconds,
                "embedding_device": device, "packages": packages,
                "files": {str(p.relative_to(stage)): sha256(p) for p in stage.rglob("*") if p.is_file()}}
        write_json(stage / "build.json", meta)
        stage.rename(output)
        return {"output": str(output), "videos": len(videos), "windows": len(windows),
                "frames": len(frame_rows), "speech_segments": len(transcript_rows)}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
