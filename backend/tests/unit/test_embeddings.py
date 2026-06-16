"""Unit tests for embedding wrapper (R1, R2)."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_stub_embed_returns_correct_dimension() -> None:
    """Stub path must return a 1536-dim vector matching text-embedding-3-small."""
    from app.services import embeddings

    with patch.object(embeddings.settings, "openai_api_key", ""):
        [vec] = await embeddings.embed(["hello"])

    assert len(vec) == embeddings.EMBED_DIM == 1536
    # Values should sit in roughly [-1, 1] (sha bytes / 128).
    assert all(-1.1 <= v <= 1.1 for v in vec[:50])


@pytest.mark.asyncio
async def test_stub_embed_is_deterministic() -> None:
    """Same input → exact same vector. Critical for reproducible RAG fixtures."""
    from app.services import embeddings

    with patch.object(embeddings.settings, "openai_api_key", ""):
        [a] = await embeddings.embed(["diversification"])
        [b] = await embeddings.embed(["diversification"])

    assert a == b


@pytest.mark.asyncio
async def test_stub_embed_differentiates_distinct_texts() -> None:
    """Different texts must yield different vectors (otherwise retrieval is broken)."""
    from app.services import embeddings

    with patch.object(embeddings.settings, "openai_api_key", ""):
        [a, b] = await embeddings.embed(["alpha", "beta"])

    assert a != b


@pytest.mark.asyncio
async def test_embed_handles_empty_input_list() -> None:
    """Empty batch returns empty list — no crash, no API call."""
    from app.services import embeddings

    out = await embeddings.embed([])
    assert out == []
