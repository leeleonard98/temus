"""RAG retrieval endpoints (R1, R6, R8)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session
from app.services import rag as rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


class RagQuery(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    k: int = Field(8, ge=1, le=50)


class RagHit(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    lang: str
    content: str
    score: float


class RagResponse(BaseModel):
    query: str
    k: int
    results: list[RagHit]


def _wrap(query: str, k: int, rows: list[dict[str, Any]]) -> RagResponse:
    return RagResponse(
        query=query,
        k=k,
        results=[RagHit(**r) for r in rows],
    )


@router.post("/semantic", response_model=RagResponse)
async def semantic(body: RagQuery, session: AsyncSession = Depends(get_session)) -> RagResponse:
    rows = await rag_service.semantic_search(session, body.query, k=body.k)
    return _wrap(body.query, body.k, rows)


@router.post("/keyword", response_model=RagResponse)
async def keyword(body: RagQuery, session: AsyncSession = Depends(get_session)) -> RagResponse:
    rows = await rag_service.keyword_search(session, body.query, k=body.k)
    return _wrap(body.query, body.k, rows)


@router.post("/hybrid", response_model=RagResponse)
async def hybrid(body: RagQuery, session: AsyncSession = Depends(get_session)) -> RagResponse:
    rows = await rag_service.hybrid_search(session, body.query, k=body.k)
    return _wrap(body.query, body.k, rows)
