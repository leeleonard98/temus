"""Embedding wrapper.

Uses OpenAI's `text-embedding-3-small` (1536 dim) when an API key is configured,
otherwise falls back to a deterministic sha256-based vector so tests and
offline dev still produce stable embeddings.
"""
from __future__ import annotations

import hashlib

from openai import AsyncOpenAI

from app.core.config import settings

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536


async def embed(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text.

    Empty inputs are padded to a single space so OpenAI doesn't reject them.
    """
    if not texts:
        return []
    if not settings.openai_api_key:
        return [_stub_embed(t) for t in texts]
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    cleaned = [t if t.strip() else " " for t in texts]
    resp = await client.embeddings.create(model=EMBED_MODEL, input=cleaned)
    return [d.embedding for d in resp.data]


def _stub_embed(text: str) -> list[float]:
    """Deterministic 1536-dim vector from sha256.

    Not a real semantic embedding — but stable per input, in [-1, 1], and
    different texts produce different vectors. Good enough for tests and the
    offline demo path; the keyword index does the heavy lifting in that mode.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    raw: list[int] = []
    while len(raw) < EMBED_DIM:
        h = hashlib.sha256(h).digest()
        raw.extend(b - 128 for b in h)
    return [v / 128.0 for v in raw[:EMBED_DIM]]
