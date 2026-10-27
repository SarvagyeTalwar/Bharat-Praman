"""Local semantic embeddings using multilingual-e5-small (384-dim).

Runs fully offline via sentence-transformers (torch backend). Requires
Python 3.14 (torch has no wheels for Python 3.15 yet). No API key, no quota.
"""
from sentence_transformers import SentenceTransformer

MODEL = SentenceTransformer("intfloat/multilingual-e5-small")
DIM = 384


def embed_texts(texts, batch=32, progress=False):
    """Embed passages (document chunks) using the e5 'passage:' prefix.

    Returns a list of float vectors (384-dim), same order as input.
    """
    return MODEL.encode(
        [f"passage: {t}" for t in texts],
        normalize_embeddings=True,
        batch_size=batch,
        show_progress_bar=progress,
    ).tolist()


def embed_query(text):
    """Embed a search query using the e5 'query:' prefix."""
    return MODEL.encode([f"query: {text}"], normalize_embeddings=True)[0].tolist()
