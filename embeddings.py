"""Local semantic embeddings using BAAI/bge-small-en-v1.5 (384-dim) by default.

Lazy-loads the SentenceTransformer model on first call (~3s cold start, ~20ms query,
~130 MB disk, ~350 MB RAM) so FastAPI starts cleanly on laptops and Railway.
Matches the 384-dim `bge_chunk_embeddings` Neo4j vector index.
Override with EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B if reverting to `qwen_chunk_embeddings`.
"""
from functools import lru_cache
import os
import threading

MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
DIM = 1024 if "qwen" in MODEL_NAME.lower() else 384
DEFAULT_TASK = "Given a question about Indian government reports, retrieve relevant passages"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_MODEL = None
_MODEL_LOCK = threading.Lock()


def _get_model():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
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
    return model.encode(
        list(texts),
        batch_size=batch,
        normalize_embeddings=True,
        show_progress_bar=progress,
    ).tolist()


@lru_cache(maxsize=512)
def embed_query(text, task=DEFAULT_TASK):
    """Embed a user search query (LRU-cached)."""
    model = _get_model()
    capped = (text or "").strip()[:400]
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
