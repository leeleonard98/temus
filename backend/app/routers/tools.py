"""Tool endpoints — wrap agent-callable tools so the demo can hit them directly."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import web_search as web_search_service

router = APIRouter(prefix="/tools", tags=["tools"])


class WebSearchIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    k: int = Field(5, ge=1, le=20)


class WebSearchHit(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchOut(BaseModel):
    query: str
    results: list[WebSearchHit]


@router.post("/web_search", response_model=WebSearchOut)
async def do_web_search(body: WebSearchIn) -> WebSearchOut:
    rows: list[dict[str, Any]] = await web_search_service.web_search(body.query, k=body.k)
    return WebSearchOut(
        query=body.query,
        results=[WebSearchHit(**r) for r in rows],
    )
