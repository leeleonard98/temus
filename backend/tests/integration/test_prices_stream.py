"""Integration test for /prices/stream — must yield ≥3 SSE frames for AAPL within 2s."""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _parse_frames(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


async def test_prices_stream_emits_frames(client: AsyncClient) -> None:
    """We expect deterministic AAPL ticks at ~50ms cadence — capped via max_ticks."""
    resp = await client.get(
        "/api/v1/prices/stream",
        params={"symbols": "AAPL", "interval_ms": 50, "persist_every": 100, "max_ticks": 5},
    )
    assert resp.status_code == 200
    frames = _parse_frames(resp.text)
    assert len(frames) >= 3
    assert all(f["symbol"] == "AAPL" for f in frames)
    assert all(isinstance(f["price"], (int, float)) for f in frames)


async def test_prices_stream_deterministic_within_second(client: AsyncClient) -> None:
    """Two consecutive ticks within the same second must have the same price."""
    resp = await client.get(
        "/api/v1/prices/stream",
        params={"symbols": "AAPL", "interval_ms": 50, "persist_every": 100, "max_ticks": 8},
    )
    frames = _parse_frames(resp.text)
    by_second: dict[str, set[float]] = {}
    for f in frames:
        sec = f["ts"][:19]
        by_second.setdefault(sec, set()).add(f["price"])
    # At least one second-bucket has multiple frames and they all share the same price.
    same_bucket = [
        sec
        for sec, prices in by_second.items()
        if len([f for f in frames if f["ts"][:19] == sec]) >= 2 and len(prices) == 1
    ]
    assert same_bucket, f"no deterministic same-second bucket; frames={frames}"


async def test_prices_stream_multiple_symbols(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/prices/stream",
        params={
            "symbols": "AAPL,MSFT,VOO",
            "interval_ms": 50,
            "persist_every": 100,
            "max_ticks": 2,
        },
    )
    frames = _parse_frames(resp.text)
    syms = {f["symbol"] for f in frames}
    assert syms == {"AAPL", "MSFT", "VOO"}
