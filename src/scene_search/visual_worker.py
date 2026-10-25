"""Standalone CLIP image inference worker, separated from video/audio decoding.

Only call with locally generated frame manifests. Outputs float32 numpy vectors.
"""
import argparse
import os
from pathlib import Path


def encode(stage, frame_rows, output, device="cpu", batch_size=2):
    # Thread controls must be applied before importing native torch libraries.
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[key] = "1"
    import numpy as np
    import torch
    from PIL import Image
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # Already configured by another torch component.
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable; retry with --device cpu")
    if not frame_rows:
        raise ValueError("No visual frames for worker")
    model = SentenceTransformer("sentence-transformers/clip-ViT-B-32", device=device)
    chunks = []
    for offset in range(0, len(frame_rows), 16):
        images = []
        for row in frame_rows[offset:offset + 16]:
            image_path = (stage / row["file"]).resolve()
            if not image_path.is_relative_to(stage):
                raise ValueError("Visual frame path leaves build stage")
            with Image.open(image_path) as image:
                images.append(image.convert("RGB"))
        print(f"CLIP worker: encoding frames {offset+1}-"
              f"{min(offset+16, len(frame_rows))}/{len(frame_rows)} on {device}",
              flush=True)
        with torch.inference_mode():
            embeddings = model.encode(
                images, batch_size=batch_size, normalize_embeddings=True,
                convert_to_numpy=True, show_progress_bar=False
            )
        chunks.append(np.asarray(embeddings, dtype="float32"))
    vector = np.concatenate(chunks, axis=0)
    if (vector.ndim != 2 or vector.shape[0] != len(frame_rows)
            or not np.isfinite(vector).all()):
        raise ValueError("Visual encoder produced invalid vectors")
    np.save(output, vector, allow_pickle=False)
    print(f"CLIP worker: saved {vector.shape[0]} embeddings", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--frames-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 32:
        parser.error("batch-size must be between 1 and 32")
    from .core import read_json
    encode(args.stage.resolve(), read_json(args.frames_json), args.output,
           args.device, args.batch_size)


if __name__ == "__main__":
    main()
