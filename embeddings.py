"""Local semantic embeddings using BAAI/bge-small-en-v1.5 (384-dim) with resilient fallback.

Lazy-loads the SentenceTransformer model on first call (~3s cold start, ~20ms query,
~130 MB disk, ~350 MB RAM) so FastAPI starts cleanly on laptops and Railway.
Matches the 384-dim `bge_chunk_embeddings` and `user_chunk_embeddings` Neo4j vector index.
If PyTorch or sentence-transformers is missing, provides deterministic normalized projection
so the server never crashes.
"""
from functools import lru_cache
import os
import threading
import logging
import math
import hashlib

logger = logging.getLogger("uvicorn.error")

MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
DIM = 1024 if "qwen" in MODEL_NAME.lower() else 384
DEFAULT_TASK = "Given a question about Indian government reports, retrieve relevant passages"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_MODEL = None
_MODEL_FAILED = False
_MODEL_LOCK = threading.Lock()


def _hash_embed(text: str, dim: int = DIM) -> list[float]:
    """Deterministic hash-based dense projection when PyTorch is not available."""
    vec = [0.0] * dim
    words = (text or "").lower().split()
    if not words:
        words = ["passage"]
    for w in words:
        h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]


def _get_model():
    global _MODEL, _MODEL_FAILED
    if _MODEL is not None:
        return _MODEL
    if _MODEL_FAILED:
        return None

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        if _MODEL_FAILED:
            return None
        try:
            import torch
            from sentence_transformers import SentenceTransformer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                torch.set_num_threads(min(os.cpu_count() or 4, 4))
            model_kwargs = {"dtype": torch.float16 if device == "cuda" else torch.float32}
            try:
                _MODEL = SentenceTransformer(
                    MODEL_NAME,
                    device=device,
                    model_kwargs=model_kwargs,
                    local_files_only=True,
                )
            except Exception:
                _MODEL = SentenceTransformer(
                    MODEL_NAME,
                    device=device,
                    model_kwargs=model_kwargs,
                )
            _MODEL.max_seq_length = 256
            _MODEL.encode(["warmup"], normalize_embeddings=True, show_progress_bar=False)
            return _MODEL
        except Exception as exc:
            logger.warning("SentenceTransformer (%s) unavailable, activating deterministic dense fallback: %s", MODEL_NAME, exc)
            _MODEL_FAILED = True
            return None


def warmup_embeddings(background: bool = True):
    """Pre-load the embedding model so the first user query has no cold-start penalty."""
    if background:
        t = threading.Thread(target=_get_model, daemon=True)
        t.start()
        return t
    return _get_model()


def embed_texts(texts, batch=32, progress=False):
    """Embed document chunks or table passages into normalized vectors."""
    if not texts:
        return []
    model = _get_model()
    if model is not None:
        try:
            return model.encode(
                list(texts),
                batch_size=batch,
                normalize_embeddings=True,
                show_progress_bar=progress,
            ).tolist()
        except Exception as exc:
            logger.warning("Model encode failed, falling back to projection: %s", exc)

    return [_hash_embed(t, dim=DIM) for t in texts]


@lru_cache(maxsize=512)
def embed_query(text, task=DEFAULT_TASK):
    """Embed a user search query (LRU-cached)."""
    capped = (text or "").strip()[:400]
    model = _get_model()
    if model is not None:
        try:
            if "qwen" in MODEL_NAME.lower():
                prompt = f"Instruct: {task}\nQuery:"
                return model.encode(
                    [capped],
                    prompt=prompt,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )[0].tolist()
            return model.encode(
                [BGE_QUERY_PREFIX + capped],
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0].tolist()
        except Exception as exc:
            logger.warning("Query encode failed, falling back to projection: %s", exc)

    return _hash_embed(BGE_QUERY_PREFIX + capped, dim=DIM)
