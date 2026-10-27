"""Semantic video scene search with isolated query model inference on macOS."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import MODES, aggregate_rank, hybrid_fuse, read_json, sha256, write_json
from .pipeline import VISUAL_MODEL, TEXT_MODEL


def _should_isolate_query(mode, platform=None):
    if mode not in ("auto", "subprocess", "in-process"):
        raise ValueError("embedding_mode must be auto, subprocess, or in-process")
    return mode == "subprocess" or (mode == "auto" and
                                    (platform or sys.platform) == "darwin")


def _query_embeddings_subprocess(queries, modality, device):
    """Encode many queries with a single isolated ML model load."""
    import numpy as np
    from .query_worker import validate_query_batch

    validate_query_batch(queries, modality)
    with tempfile.TemporaryDirectory(prefix="scene-search-query-") as td:
        temporary = Path(td)
        prompt = temporary / "queries.json"
        result = temporary / "embeddings.npy"
        write_json(prompt, {"queries": queries, "modality": modality})
        env = os.environ.copy()
        for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
            env[key] = "1"
        command = [sys.executable, "-X", "faulthandler", "-m",
                   "scene_search.query_worker", "--query-json", str(prompt),
                   "--output", str(result), "--device", device]
        try:
            process = subprocess.run(command, env=env, check=False, timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Query encoder timed out after 600 seconds") from exc
        if process.returncode and env.get("HF_HUB_OFFLINE") == "1":
            raise RuntimeError(
                "Offline query worker failed. Check whether both the CLIP and "
                "MiniLM Hugging Face models are fully cached on this Mac; "
                "see worker logs above. No TLS verification was disabled."
            )
        if process.returncode:
            raise RuntimeError(
                f"Query encoder subprocess exited with code {process.returncode}. "
                "See worker logs above. On Mac, try --device mps if available; "
                "native crashes may require a different compatible PyTorch build."
            )
        if not result.is_file():
            raise RuntimeError("Query encoder produced no embedding file")
        vector = np.load(result, allow_pickle=False)
        if (vector.ndim != 2 or vector.shape[0] != len(queries)
                or vector.shape[1] < 1 or not np.isfinite(vector).all()):
            raise ValueError("Invalid query embedding dimensions or values")
        return np.ascontiguousarray(vector, dtype="float32")


def _query_embedding_subprocess(query, modality, device):
    """Single-query compatibility path for UI and CLI search."""
    return _query_embeddings_subprocess([query], modality, device)


class SearchEngine:
    """Load trusted local indexes; protect application from native query crashes."""

    def __init__(self, root, device="auto", embedding_mode="auto"):
        import faiss
        self.root = Path(root).resolve()
        self.meta = read_json(self.root / "build.json")
        if self.meta.get("schema_version") != 1:
            raise ValueError("Unsupported index schema")
        if self.meta.get("visual_model") != VISUAL_MODEL or self.meta.get("text_model") != TEXT_MODEL:
            raise ValueError("Unsupported index embedding models")
        for name, digest in self.meta["files"].items():
            path = (self.root / name).resolve()
            if not path.is_relative_to(self.root) or sha256(path) != digest:
                raise ValueError(f"Index integrity check failed: {name}")
        self.windows = read_json(self.root / "windows.json")
        self.by_id = {w["id"]: w for w in self.windows}
        self.videos = {v["id"]: v for v in read_json(self.root / "corpus.json")["videos"]}
        self.frames = read_json(self.root / "frames.json")
        self.segments = read_json(self.root / "segments.json")
        self.visual_index = faiss.read_index(str(self.root / "visual.faiss"))
        self.text_index = (faiss.read_index(str(self.root / "transcript.faiss"))
                           if self.segments else None)
        if self.visual_index.ntotal != len(self.frames) or (
            self.text_index is not None and self.text_index.ntotal != len(self.segments)
        ):
            raise ValueError("Index and metadata row counts differ")
        if device not in ("auto", "cpu", "mps", "cuda"):
            raise ValueError("Invalid search device")
        if embedding_mode == "auto":
            embedding_mode = os.environ.get("SCENE_EMBEDDING_MODE", "auto")
        self.isolate = _should_isolate_query(embedding_mode)
        self.device = device
        self._visual_model = self._text_model = None

    def _rank(self, query, modality):
        import numpy as np
        if modality == "visual":
            model_name, index, rows = VISUAL_MODEL, self.visual_index, self.frames
        else:
            if self.text_index is None:
                return []
            model_name, index, rows = TEXT_MODEL, self.text_index, self.segments
        if self.isolate:
            vector = _query_embedding_subprocess(query, modality, self.device)
        else:
            from sentence_transformers import SentenceTransformer
            device = "cpu" if self.device == "auto" else self.device
            if modality == "visual":
                if self._visual_model is None:
                    self._visual_model = SentenceTransformer(model_name, device=device)
                model = self._visual_model
            else:
                if self._text_model is None:
                    self._text_model = SentenceTransformer(model_name, device=device)
                model = self._text_model
            vector = np.ascontiguousarray(
                model.encode([query], normalize_embeddings=True, convert_to_numpy=True),
                dtype="float32")
        if vector.shape[1] != index.d:
            raise ValueError(f"Query embedding dimension {vector.shape[1]} differs from "
                             f"FAISS index dimension {index.d}")
        scores, indices = index.search(vector, index.ntotal)
        return aggregate_rank(scores[0], indices[0], rows)

    def rankings_batch(self, queries, modality):
        """Evaluate many queries of one modality with one model load on macOS."""
        from .query_worker import validate_query_batch
        validate_query_batch(queries, modality)
        if not self.isolate:
            return [self.rankings(query, modality) for query in queries]
        if modality == "transcript" and self.text_index is None:
            return [[] for _ in queries]
        matrix = _query_embeddings_subprocess(queries, modality, self.device)
        index, rows = ((self.visual_index, self.frames) if modality == "visual"
                       else (self.text_index, self.segments))
        if matrix.shape[1] != index.d:
            raise ValueError("Query matrix dimension differs from FAISS index")
        scores, indices = index.search(matrix, index.ntotal)
        return [aggregate_rank(row_scores, row_indices, rows)
                for row_scores, row_indices in zip(scores, indices)]

    def rankings(self, query, mode="hybrid"):
        query = query.strip()
        if not query or len(query) > 500:
            raise ValueError("Query must contain 1–500 characters")
        if mode not in MODES:
            raise ValueError("Mode must be visual, transcript or hybrid")
        if mode == "visual":
            return self._rank(query, "visual")
        if mode == "transcript":
            return self._rank(query, "transcript")
        return hybrid_fuse(query, self._rank(query, "visual"), self._rank(query, "transcript"))

    def search(self, query, mode="hybrid", k=5):
        if not 1 <= k <= 100:
            raise ValueError("k must be between 1 and 100")
        results = []
        for wid, score in self.rankings(query, mode)[:k]:
            w = self.by_id[wid]
            frame = next((f for f in self.frames if wid in f["window_ids"]), None)
            results.append({**w, "score": score, "mode": mode,
                "title": self.videos[w["video_id"]]["title"],
                "video_path": self.videos[w["video_id"]]["path"],
                "thumbnail": str(self.root / frame["file"]) if frame else None,
                "transcript": " ".join(s["text"] for s in self.segments if wid in s["window_ids"])})
        return results
