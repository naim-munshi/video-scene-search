"""Offline video ingestion. An incomplete build is never published."""
import importlib.metadata
import math
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import make_windows, overlap, read_json, sha256, write_json

VISUAL_MODEL = "sentence-transformers/clip-ViT-B-32"
TEXT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_manifest(path):
    path = Path(path).resolve()
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a JSON object")
    videos = data.get("videos")
    if not isinstance(videos, list) or not 1 <= len(videos) <= 200:
        raise ValueError("Manifest must contain 1–200 video entries")
    ids = set()
    for v in videos:
        if not isinstance(v, dict):
            raise ValueError("Every video entry must be an object")
        vid = v.get("id", "")
        if not isinstance(vid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", vid) or vid in ids:
            raise ValueError("Video IDs must be unique and contain only letters, digits, _ or -")
        ids.add(vid)
        if not all(str(v.get(k, "")).strip() for k in ("title", "license", "source", "attribution")):
            raise ValueError(f"Missing provenance for {vid}")
        if v.get("rights_confirmed") is not True:
            raise ValueError(f"Confirm permission/licensing for {vid} before ingestion")
        media_path = v.get("path")
        if not isinstance(media_path, str) or not media_path.strip() or chr(0) in media_path:
            raise ValueError(f"Missing or invalid video path for {vid}")
        p = (path.parent / media_path).resolve()
        if not p.is_file():
            raise ValueError(f"Video missing: {p}")
        v["path"] = str(p)
    return videos


def extract_frames(video_path, video_id, stage, frame_seconds, window_seconds):
    """Decode frames through PyAV, avoiding OpenCV/PyAV FFmpeg dylib collisions.

    Uses presentation timestamps from the video stream for seeking alignment.
    Constant-frame-rate MP4s are recommended; the last partial window is kept.
    """
    import av
    from PIL import Image

    frame_rows = []
    with av.open(str(video_path), mode="r") as container:
        if not container.streams.video:
            raise ValueError(f"No video stream: {video_id}")
        stream = container.streams.video[0]
        # Prefer video stream duration to avoid audio padding extending windows.
        duration = (float(stream.duration * stream.time_base)
                    if stream.duration is not None and stream.time_base else None)
        if (duration is None or not math.isfinite(duration) or duration <= 0) and container.duration:
            duration = float(container.duration / av.time_base)
        if duration is None or not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Missing/invalid video duration: {video_id}")
        windows = make_windows(video_id, duration, window_seconds)
        fps = float(stream.average_rate) if stream.average_rate else None
        time_origin = (float(stream.start_time * stream.time_base)
                       if stream.start_time is not None and stream.time_base else 0.0)
        next_sample = 0.0
        frames_decoded = 0
        for frame in container.decode(stream):
            frames_decoded += 1
            timestamp = (float(frame.time) - time_origin if frame.time is not None else
                         (frames_decoded - 1) / fps if fps and fps > 0 else float('nan'))
            if not math.isfinite(timestamp):
                raise ValueError(f"Cannot determine frame timestamps: {video_id}")
            if timestamp < -1e-5:
                continue
            timestamp = max(0.0, timestamp)
            if timestamp + 1e-8 < next_sample or timestamp >= duration:
                continue
            name = f"frames/{video_id}-{frames_decoded-1:08d}.jpg"
            picture = frame.to_image().convert("RGB")
            if picture.width > 640:
                picture = picture.resize((640, max(1, round(picture.height * 640 / picture.width))),
                                         resample=Image.Resampling.BILINEAR)
            picture.save(stage / name, format="JPEG")
            window_id = windows[min(int(timestamp // window_seconds), len(windows) - 1)]["id"]
            frame_rows.append({"video_id": video_id, "timestamp": timestamp,
                               "file": name, "window_ids": [window_id]})
            next_sample += frame_seconds
        if frames_decoded == 0 or not frame_rows:
            raise ValueError(f"No decodable frames: {video_id}")
        # A truncated input should not quietly appear successfully indexed.
        if stream.frames and fps and fps > 0 and frames_decoded < stream.frames - max(2, fps):
            raise ValueError(f"Video decoding ended early: {video_id}")
    return duration, windows, frame_rows


def _isolate_visual(mode, platform=None):
    """Use a fresh process for native visual inference on macOS by default."""
    if mode not in ("auto", "subprocess", "in-process"):
        raise ValueError("embedding_mode must be auto, subprocess, or in-process")
    return mode == "subprocess" or (mode == "auto" and
                                    (platform if platform is not None else sys.platform) == "darwin")


def _encode_visual_subprocess(stage, frame_rows, device, batch_size):
    """Keep PyTorch convolution outside of the Whisper/PyAV ingestion process."""
    from .core import write_json, read_json
    import numpy as np

    inputs = stage / ".visual-input.json"
    output = stage / ".visual-output.npy"
    write_json(inputs, frame_rows)
    env = __import__("os").environ.copy()
    # These are set before torch loads in the worker; do not mutate the parent.
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env[variable] = "1"
    cmd = [sys.executable, "-X", "faulthandler", "-m", "scene_search.visual_worker",
           "--stage", str(stage), "--frames-json", str(inputs),
           "--output", str(output), "--device", device,
           "--batch-size", str(batch_size)]
    print(f"Starting isolated visual encoder: device={device}, batch_size={batch_size}",
          file=sys.stderr, flush=True)
    try:
        proc = subprocess.run(cmd, env=env, check=False)
        if proc.returncode != 0:
            signal_hint = " (native crash)" if proc.returncode < 0 else ""
            raise RuntimeError(
                f"Visual encoder subprocess failed: exit={proc.returncode}{signal_hint}. "
                "On Apple Silicon, check torch.backends.mps.is_available() and "
                "retry ingest with --device mps into a fresh output directory. "
                "Save the subprocess traceback if it still fails."
            )
        if not output.is_file():
            raise RuntimeError("Visual encoder finished without a vector file")
        matrix = np.load(output, allow_pickle=False)
        if (matrix.ndim != 2 or matrix.shape[0] != len(frame_rows)
                or matrix.shape[1] < 1 or not np.isfinite(matrix).all()):
            raise ValueError("Visual worker returned invalid embeddings")
        return np.ascontiguousarray(matrix, dtype="float32")
    finally:
        inputs.unlink(missing_ok=True)
        output.unlink(missing_ok=True)


def build(manifest, output, whisper_model="base", language=None, frame_seconds=2.0,
          window_seconds=10.0, device="cpu", embedding_mode="auto", visual_batch_size=2):
    if not all(math.isfinite(x) and x > 0 for x in (frame_seconds, window_seconds)):
        raise ValueError("Sampling and window intervals must be finite and positive")
    if frame_seconds > window_seconds:
        raise ValueError("Frame interval must not exceed the window size")
    if not isinstance(visual_batch_size, int) or not 1 <= visual_batch_size <= 32:
        raise ValueError("visual_batch_size must be between 1 and 32")
    isolate = _isolate_visual(embedding_mode)
    videos = load_manifest(manifest)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Output already exists; use a new directory for each build")
    import faiss
    import numpy as np
    from PIL import Image
    from faster_whisper import WhisperModel

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".scene-build-", dir=output.parent))
    try:
        (stage / "frames").mkdir()
        (stage / "transcripts").mkdir()
        # CTranslate2 uses CPU int8 on Apple Silicon; MPS is for embeddings only.
        whisper = WhisperModel(whisper_model, device="cpu", compute_type="int8")
        windows, frame_rows, transcript_rows = [], [], []
        for v in videos:
            print(f"Processing {v['id']}: {v['title']}", file=sys.stderr, flush=True)
            v["sha256"] = sha256(v["path"])
            duration, vw, samples = extract_frames(v["path"], v["id"], stage,
                                                   frame_seconds, window_seconds)
            v["duration"] = duration
            windows.extend(vw)
            frame_rows.extend(samples)
            print(f"Decoded {v['id']}: {len(samples)} sampled frames; transcribing speech", file=sys.stderr, flush=True)
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
            print(f"Transcribed {v['id']}: {len(transcript)} speech segments", file=sys.stderr, flush=True)
        print(f"Encoding {len(frame_rows)} visual frames", file=sys.stderr, flush=True)
        if isolate:
            vectors = _encode_visual_subprocess(stage, frame_rows, device, visual_batch_size)
        else:
            from sentence_transformers import SentenceTransformer
            visual = SentenceTransformer(VISUAL_MODEL, device=device)
            matrix = []
            for offset in range(0, len(frame_rows), 32):
                images = []
                for row in frame_rows[offset:offset + 32]:
                    with Image.open(stage / row["file"]) as im:
                        images.append(im.convert("RGB"))
                matrix.append(visual.encode(images, batch_size=visual_batch_size,
                                            normalize_embeddings=True, convert_to_numpy=True))
            vectors = np.ascontiguousarray(np.concatenate(matrix), dtype="float32")
            del visual
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(stage / "visual.faiss"))
        print(f"Encoded visual frames; encoding {len(transcript_rows)} speech segments", file=sys.stderr, flush=True)
        if transcript_rows:
            from sentence_transformers import SentenceTransformer
            text = SentenceTransformer(TEXT_MODEL, device=device)
            vectors = np.ascontiguousarray(text.encode([r["text"] for r in transcript_rows],
                batch_size=32, normalize_embeddings=True, convert_to_numpy=True), dtype="float32")
            index = faiss.IndexFlatIP(vectors.shape[1])
            index.add(vectors)
            faiss.write_index(index, str(stage / "transcript.faiss"))
        print("Writing index files and build manifest", file=sys.stderr, flush=True)
        write_json(stage / "windows.json", windows)
        write_json(stage / "frames.json", frame_rows)
        write_json(stage / "segments.json", transcript_rows)
        write_json(stage / "corpus.json", {"videos": videos})
        packages = {p: importlib.metadata.version(p) for p in (
            "numpy", "faiss-cpu", "av", "faster-whisper",
            "sentence-transformers", "torch", "transformers", "streamlit")}
        meta = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "visual_model": VISUAL_MODEL, "text_model": TEXT_MODEL,
                "whisper_model": whisper_model, "whisper_device": "cpu", "language": language,
                "frame_seconds": frame_seconds, "window_seconds": window_seconds,
                "embedding_device": device, "embedding_mode": "subprocess" if isolate else "in-process",
                "visual_batch_size": visual_batch_size, "packages": packages,
                "files": {str(p.relative_to(stage)): sha256(p) for p in stage.rglob("*") if p.is_file()}}
        write_json(stage / "build.json", meta)
        stage.rename(output)
        return {"output": str(output), "videos": len(videos), "windows": len(windows),
                "frames": len(frame_rows), "speech_segments": len(transcript_rows)}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
