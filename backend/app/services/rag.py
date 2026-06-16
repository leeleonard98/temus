"""RAG retrieval — semantic, keyword, and hybrid (R1, R6, R8).

Queries the chunks table directly. Each function returns a list of dicts
ready to render: `{chunk_id, doc_id, title, lang, content, score}`.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import embed

DEFAULT_K = 8


async def semantic_search(
    session: AsyncSession, query: str, k: int = DEFAULT_K
) -> list[dict[str, Any]]:
    """Top-k chunks by cosine distance to the query embedding (R1)."""
    [vec] = await embed([query])
    # Force full recall — at our scale (~50–1000 chunks) the planner's IVFFLAT
    # index can miss hits when the index is barely trained (probes=1 default).
    # Setting probes=lists is equivalent to a seq scan for correctness while
    # keeping the index path available for larger corpora later.
    await session.execute(text("SET LOCAL ivfflat.probes = 100"))
    stmt = text(
        """
        SELECT
            c.id::text  AS chunk_id,
            c.document_id::text AS doc_id,
            d.title AS title,
            d.lang  AS lang,
            c.content AS content,
            1 - (c.embedding <=> CAST(:q AS vector)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> CAST(:q AS vector)
        LIMIT :k
        """
    )
    rows = (await session.execute(stmt, {"q": str(vec), "k": k})).mappings().all()
    return [dict(r) for r in rows]


async def keyword_search(
    session: AsyncSession, query: str, k: int = DEFAULT_K
) -> list[dict[str, Any]]:
    """Top-k chunks by tsvector full-text rank (R6)."""
    stmt = text(
        """
        SELECT
            c.id::text  AS chunk_id,
            c.document_id::text AS doc_id,
            d.title AS title,
            d.lang  AS lang,
            c.content AS content,
            ts_rank_cd(c.content_tsv, plainto_tsquery('english', :q)) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.content_tsv @@ plainto_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :k
        """
    ).bindparams(bindparam("q"), bindparam("k"))
    rows = (await session.execute(stmt, {"q": query, "k": k})).mappings().all()
    return [dict(r) for r in rows]


async def hybrid_search(
    session: AsyncSession, query: str, k: int = DEFAULT_K
) -> list[dict[str, Any]]:
    """Reciprocal-rank-fusion over semantic + keyword (R8).

    Each retriever returns 2k results; we fuse with rrf_score = sum(1/(60+rank))
    across the two lists. Chunks present in both lists naturally rise to the top.
    """
    sem = await semantic_search(session, query, k=k * 2)
    kw = await keyword_search(session, query, k=k * 2)

    by_id: dict[str, dict[str, Any]] = {}
    rrf_const = 60

    def _accumulate(rows: list[dict[str, Any]]) -> None:
        for rank, row in enumerate(rows):
            cid = row["chunk_id"]
            entry = by_id.setdefault(cid, {**row, "score": 0.0})
            entry["score"] += 1.0 / (rrf_const + rank + 1)

    _accumulate(sem)
    _accumulate(kw)

    fused = sorted(by_id.values(), key=lambda r: r["score"], reverse=True)
    return fused[:k]
