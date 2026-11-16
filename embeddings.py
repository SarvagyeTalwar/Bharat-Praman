"""Local semantic embeddings using Qwen/Qwen3-Embedding-0.6B (1024-dim).

Lazy-loads the SentenceTransformer model on first call so FastAPI starts
instantly. Matches the 1024-dim `qwen_chunk_embeddings` and
`budget_table_embeddings` Neo4j vector indexes.
"""
from functools import lru_cache
import os
import threading

MODEL_NAME = os.getenv("QWEN_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
DIM = 1024
DEFAULT_TASK = "Given a question about Indian government reports, retrieve relevant passages"

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
    """Pre-load Qwen3-Embedding-0.6B so the first user query has no cold-start penalty."""
    if background:
        t = threading.Thread(target=_get_model, daemon=True)
        t.start()
        return t
    return _get_model()


def embed_texts(texts, batch=16, progress=False):
    """Embed document chunks or table passages into 1024-dim normalized vectors."""
    if not texts:
        return []
    model = _get_model()
    return model.encode(
        list(texts),
        batch_size=batch,
        normalize_embeddings=True,
        show_progress_bar=progress,
    ).tolist()


@lru_cache(maxsize=256)
def embed_query(text, task=DEFAULT_TASK):
    """Embed a user search query using the Qwen instruction prefix (LRU-cached)."""
    model = _get_model()
    prompt = f"Instruct: {task}\nQuery:"
    capped = (text or "").strip()[:400]
    return model.encode(
        [capped],
        prompt=prompt,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].tolist()
