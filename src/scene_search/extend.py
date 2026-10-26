"""Append exactly one video to a completed trusted local FAISS index.

Reuses the first index's frames, transcripts and stored vectors without
transcribing or encoding old videos again. Publishes a new atomic index
directory only on success. Never changes the original index or annotations.
"""
import importlib.metadata
import math
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import overlap, read_json, sha256, write_json
from .pipeline import (VISUAL_MODEL, TEXT_MODEL, _encode_visual_subprocess,
                       _isolate_visual, extract_frames, load_manifest)


def extension_plan(base_root, manifest, output):
    base = Path(base_root).expanduser().resolve()
    destination = Path(output).expanduser().resolve()
    if destination.exists() or destination == base:
        raise ValueError("New output directory must not exist or overwrite the base index")
    metadata = read_json(base / "build.json")
    if metadata.get("schema_version") != 1 or (
        metadata.get("visual_model"), metadata.get("text_model")
    ) != (VISUAL_MODEL, TEXT_MODEL):
        raise ValueError("Incompatible base index model schema")
    for required in ("whisper_model", "language", "embedding_device",
                     "frame_seconds", "window_seconds", "visual_batch_size"):
        if required not in metadata:
            raise ValueError(f"Base index missing configuration: {required}")
    if not isinstance(metadata.get("files"), dict):
        raise ValueError("Base index missing file checksum manifest")
    for rel, digest in metadata["files"].items():
        path = (base / rel).resolve()
        if not path.is_relative_to(base) or not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Base index integrity check failed: {rel}")
    old = read_json(base / "corpus.json")["videos"]
    proposed = load_manifest(manifest)
    if len(proposed) != len(old) + 1:
        raise ValueError("Incremental extension requires exactly one additional video")
    for current, earlier in zip(proposed[:-1], old):
        for key in ("id", "path", "title", "source", "license", "attribution"):
            if current.get(key) != earlier.get(key):
                raise ValueError(f"Prior video changed ({key}); full rebuild required")
        if sha256(current["path"]) != earlier.get("sha256"):
            raise ValueError(f"Source video changed: {current['id']}; rebuild required")
    if proposed[-1]["id"] in {v["id"] for v in old}:
        raise ValueError("Additional video ID must be unique")
    return {"base": base, "output": destination, "metadata": metadata,
            "original": old, "proposed": proposed,
            "added": proposed[-1]}


def _stage_base_frames(base, stage, frames):
    """Copy trusted old thumbnails; never hardlink writable original artifacts."""
    for frame in frames:
        rel = Path(frame["file"])
        source = (base / rel).resolve()
        destination = (stage / rel).resolve()
        if (not source.is_relative_to(base) or not destination.is_relative_to(stage)
                or not source.is_file() or not destination.parent.is_dir()):
            raise ValueError(f"Unsafe base frame reference: {rel}")
        shutil.copy2(source, destination)


def extend(base_index, manifest, output, device=None):
    plan = extension_plan(base_index, manifest, output)
    base = plan["base"]
    destination = plan["output"]
    previous = plan["metadata"]
    device = device or previous["embedding_device"]
    if device not in ("cpu", "mps", "cuda"):
        raise ValueError("Specify a valid embedding device")
    import faiss
    import numpy as np
    from faster_whisper import WhisperModel

    old_windows = read_json(base / "windows.json")
    old_frames = read_json(base / "frames.json")
    old_segments = read_json(base / "segments.json")
    original_visual = faiss.read_index(str(base / "visual.faiss"))
    if original_visual.ntotal != len(old_frames):
        raise ValueError("Original visual index row count mismatches frame metadata")
    if old_segments:
        original_text = faiss.read_index(str(base / "transcript.faiss"))
        if original_text.ntotal != len(old_segments):
            raise ValueError("Original transcript index row count mismatches segments")
    else:
        original_text = None

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".scene-extend-", dir=destination.parent))
    try:
        (stage / "frames").mkdir()
        (stage / "transcripts").mkdir()
        _stage_base_frames(base, stage, old_frames)
        for video in plan["original"]:
            name = f"{video['id']}.json"
            source = (base / "transcripts" / name).resolve()
            if not source.is_relative_to(base) or not source.is_file():
                raise ValueError(f"Missing original transcript file: {name}")
            shutil.copy2(source, stage / "transcripts" / name)

        video = plan["added"]
        print(f"Appending {video['id']}; preserving {len(plan['original'])} prior videos",
              file=sys.stderr, flush=True)
        video["sha256"] = sha256(video["path"])
        duration, new_windows, new_frames = extract_frames(
            video["path"], video["id"], stage,
            float(previous["frame_seconds"]), float(previous["window_seconds"]))
        video["duration"] = duration
        print(f"Decoded {len(new_frames)} new frames; transcribing new video",
              file=sys.stderr, flush=True)
        whisper = WhisperModel(previous["whisper_model"], device="cpu",
                               compute_type="int8")
        speech, info = whisper.transcribe(
            video["path"], language=previous["language"], vad_filter=True,
            condition_on_previous_text=False)
        new_segments = []
        for segment in speech:
            start, end = max(0, segment.start), min(duration, segment.end)
            if segment.text.strip() and end > start:
                new_segments.append({
                    "video_id": video["id"], "start": start, "end": end,
                    "text": segment.text.strip(),
                    "window_ids": [w["id"] for w in new_windows
                                   if overlap(start, end, w["start"], w["end"]) > 0]})
        video["detected_language"] = info.language
        write_json(stage / "transcripts" / f"{video['id']}.json", new_segments)
        print(f"New video: {len(new_segments)} speech segments; encoding new frames",
              file=sys.stderr, flush=True)

        # Reuse the stored FAISS vectors for the prior videos.
        isolate = _isolate_visual("auto")
        if isolate:
            new_vectors = _encode_visual_subprocess(
                stage, new_frames, device, int(previous["visual_batch_size"]))
        else:
            from PIL import Image
            from sentence_transformers import SentenceTransformer
            visual = SentenceTransformer(VISUAL_MODEL, device=device)
            chunks = []
            for offset in range(0, len(new_frames), 16):
                images = []
                for row in new_frames[offset:offset + 16]:
                    with Image.open(stage / row["file"]) as im:
                        images.append(im.convert("RGB"))
                chunks.append(visual.encode(
                    images, batch_size=int(previous["visual_batch_size"]),
                    normalize_embeddings=True, convert_to_numpy=True))
            new_vectors = np.ascontiguousarray(
                np.concatenate(chunks), dtype="float32")
            del visual
        if new_vectors.shape[1] != original_visual.d:
            raise ValueError("New CLIP vector dimension differs from old index")
        original_visual.add(np.ascontiguousarray(new_vectors, dtype="float32"))
        faiss.write_index(original_visual, str(stage / "visual.faiss"))

        if new_segments:
            from sentence_transformers import SentenceTransformer
            text_model = SentenceTransformer(TEXT_MODEL, device=device)
            embeddings = np.ascontiguousarray(text_model.encode(
                [r["text"] for r in new_segments], batch_size=32,
                normalize_embeddings=True, convert_to_numpy=True), dtype="float32")
            if original_text is None:
                original_text = faiss.IndexFlatIP(embeddings.shape[1])
            if embeddings.shape[1] != original_text.d:
                raise ValueError("New transcript embedding dimension mismatch")
            original_text.add(embeddings)
            del text_model
        if original_text is not None:
            faiss.write_index(original_text, str(stage / "transcript.faiss"))

        write_json(stage / "corpus.json", {
            "videos": [*plan["original"], video]})
        write_json(stage / "windows.json", [*old_windows, *new_windows])
        write_json(stage / "frames.json", [*old_frames, *new_frames])
        write_json(stage / "segments.json", [*old_segments, *new_segments])
        packages = {p: importlib.metadata.version(p) for p in (
            "numpy", "faiss-cpu", "av", "faster-whisper",
            "sentence-transformers", "torch", "transformers", "streamlit")}
        new_metadata = {
            **previous,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "packages": packages,
            "embedding_device": device,
            "embedding_mode": "subprocess" if isolate else "in-process",
            "ingest_strategy": "append_one_video",
            "base_build_sha256": sha256(base / "build.json"),
            "files": {str(p.relative_to(stage)): sha256(p)
                      for p in stage.rglob("*") if p.is_file()},
        }
        write_json(stage / "build.json", new_metadata)
        if destination.exists():
            raise ValueError("Output appeared during extension; no overwrite allowed")
        stage.rename(destination)
        return {"output": str(destination), "videos": len(plan["proposed"]),
                "windows": len(old_windows) + len(new_windows),
                "frames": len(old_frames) + len(new_frames),
                "speech_segments": len(old_segments) + len(new_segments),
                "reused_frames": len(old_frames),
                "reused_speech_segments": len(old_segments),
                "added_video": video["id"]}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
