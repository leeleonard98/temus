"""Integration tests for RAG endpoints (R1, R6, R8).

Each test seeds two tiny documents, embeds via the deterministic stub, and
asserts that semantic / keyword / hybrid search each return at least one
on-topic result.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.services.embeddings import embed

pytestmark = pytest.mark.asyncio


async def _seed_corpus(session: AsyncSession) -> tuple[Document, Document]:
    """Insert two minimal documents with a couple of chunks each."""
    doc_a = Document(
        id=uuid.uuid4(),
        source_uri="test/a.md",
        title="Diversification Basics",
        lang="en",
        doc_type="markdown",
        metadata_json={},
    )
    doc_b = Document(
        id=uuid.uuid4(),
        source_uri="test/b.md",
        title="Index Funds",
        lang="en",
        doc_type="markdown",
        metadata_json={},
    )
    session.add_all([doc_a, doc_b])
    await session.flush()

    contents = [
        (doc_a, "Diversification spreads risk across many assets and sectors."),
        (doc_a, "A globally diversified portfolio reduces idiosyncratic risk."),
        (doc_b, "Index funds track a market index at low cost."),
        (doc_b, "ETFs are tax efficient because of in-kind redemption."),
    ]
    vectors = await embed([c for _, c in contents])
    for ord_, ((doc, content), vec) in enumerate(zip(contents, vectors, strict=True)):
        session.add(
            Chunk(
                document_id=doc.id,
                ord=ord_,
                content=content,
                token_count=len(content) // 4,
                embedding=vec,
            )
        )
    await session.flush()
    # Populate tsvector server-side, mirroring the ingestion script.
    await session.execute(
        text(
            "UPDATE chunks SET content_tsv = to_tsvector('english', content)"
        )
    )
    await session.commit()
    return doc_a, doc_b


async def test_semantic_search_returns_results(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    await _seed_corpus(async_session)

    res = await client.post(
        "/api/v1/rag/semantic",
        json={"query": "diversification", "k": 3},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "diversification"
    assert len(body["results"]) >= 1
    # Each hit has the documented shape.
    hit = body["results"][0]
    assert {"chunk_id", "doc_id", "title", "lang", "content", "score"} <= set(hit)


async def test_keyword_search_finds_term(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    await _seed_corpus(async_session)

    res = await client.post(
        "/api/v1/rag/keyword",
        json={"query": "diversification", "k": 5},
    )

    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) >= 1
    # The Diversification doc must appear in the keyword hits.
    titles = {r["title"] for r in body["results"]}
    assert "Diversification Basics" in titles


async def test_hybrid_search_fuses_semantic_and_keyword(
    client: AsyncClient, async_session: AsyncSession
) -> None:
    await _seed_corpus(async_session)

    res = await client.post(
        "/api/v1/rag/hybrid",
        json={"query": "diversification index", "k": 4},
    )

    assert res.status_code == 200
    body = res.json()
    assert 1 <= len(body["results"]) <= 4
    # RRF scores are positive and the list is sorted descending.
    scores = [r["score"] for r in body["results"]]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


async def test_rag_validates_input(client: AsyncClient) -> None:
    """Empty query → 422; over-large k → 422."""
    r1 = await client.post("/api/v1/rag/semantic", json={"query": "", "k": 3})
    assert r1.status_code == 422

    r2 = await client.post("/api/v1/rag/semantic", json={"query": "ok", "k": 1000})
    assert r2.status_code == 422
