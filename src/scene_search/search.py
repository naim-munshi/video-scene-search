from pathlib import Path

from .core import MODES, aggregate_rank, fuse, read_json, sha256


class SearchEngine:
    """Load only trusted locally generated artifacts; FAISS is a native file format."""

    def __init__(self, root, device="cpu"):
        import faiss
        self.root = Path(root).resolve()
        self.meta = read_json(self.root / "build.json")
        if self.meta.get("schema_version") != 1:
            raise ValueError("Unsupported index schema")
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
        self.device = device
        self._visual_model = self._text_model = None

    def _rank(self, query, modality):
        import numpy as np
        from sentence_transformers import SentenceTransformer
        if modality == "visual":
            if self._visual_model is None:
                self._visual_model = SentenceTransformer(self.meta["visual_model"], device=self.device)
            model, index, rows = self._visual_model, self.visual_index, self.frames
        else:
            if self.text_index is None:
                return []
            if self._text_model is None:
                self._text_model = SentenceTransformer(self.meta["text_model"], device=self.device)
            model, index, rows = self._text_model, self.text_index, self.segments
        vector = np.ascontiguousarray(model.encode([query], normalize_embeddings=True,
                                                   convert_to_numpy=True), dtype="float32")
        # Full scan is intentional for this small corpus: exact max per window and full-rank RRF.
        scores, indices = index.search(vector, index.ntotal)
        return aggregate_rank(scores[0], indices[0], rows)

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
        return fuse(self._rank(query, "visual"), self._rank(query, "transcript"))

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
