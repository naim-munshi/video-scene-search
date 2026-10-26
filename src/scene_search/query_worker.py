"""Isolated text-query embedding worker for macOS native inference stability.

Only two fixed repository model identifiers are allowed. Query contents are
read from a local temporary JSON file, not the process command line.
"""
import argparse
import os
import sys
from pathlib import Path

VISUAL_MODEL = "sentence-transformers/clip-ViT-B-32"
TEXT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def select_device(requested, torch_module):
    if requested == "auto":
        return "mps" if torch_module.backends.mps.is_available() else "cpu"
    if requested == "mps" and not torch_module.backends.mps.is_available():
        raise RuntimeError("MPS not available; select --device cpu")
    if requested not in ("cpu", "mps", "cuda"):
        raise ValueError("Invalid embedding device")
    if requested == "cuda" and not torch_module.cuda.is_available():
        raise RuntimeError("CUDA not available")
    return requested


def validate_query_batch(queries, modality):
    if modality not in ("visual", "transcript"):
        raise ValueError("Modality must be visual or transcript")
    if not isinstance(queries, list) or not 1 <= len(queries) <= 128:
        raise ValueError("Query batch must contain 1–128 queries")
    if any(not isinstance(query, str) or not 1 <= len(query.strip()) <= 500
           for query in queries):
        raise ValueError("Every query must contain 1–500 characters")


def encode_many(queries, modality, output, device="auto"):
    """Encode 1–128 queries with one model load and one worker process."""
    validate_query_batch(queries, modality)
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[key] = "1"
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    selected = select_device(device, torch)
    model_id = VISUAL_MODEL if modality == "visual" else TEXT_MODEL
    print(f"Query worker: {len(queries)} {modality} queries on {selected}", file=sys.stderr, flush=True)
    model = SentenceTransformer(model_id, device=selected)
    with torch.inference_mode():
        matrix = model.encode(queries, batch_size=8, normalize_embeddings=True,
                              convert_to_numpy=True, show_progress_bar=False)
    matrix = np.asarray(matrix, dtype="float32")
    if (matrix.ndim != 2 or matrix.shape[0] != len(queries)
            or not np.isfinite(matrix).all()):
        raise ValueError("Invalid query embedding matrix")
    np.save(output, matrix, allow_pickle=False)


def encode_query(query, modality, output, device="auto"):
    """Backward-compatible single-query entry point."""
    return encode_many([query], modality, output, device)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"),
                        default="auto")
    args = parser.parse_args()
    from .core import read_json
    data = read_json(args.query_json)
    if "queries" in data:
        encode_many(data["queries"], data["modality"], args.output, args.device)
    else:
        encode_query(data["query"], data["modality"], args.output, args.device)


if __name__ == "__main__":
    main()
