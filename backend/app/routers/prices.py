"""Streaming prices endpoint (AC6 — simulated random walk).

Emits one SSE frame per ~500ms per symbol, with a deterministic price derived
from `(symbol, second-bucket)` so two clients see the same numbers (good for
demos). Every Nth tick is persisted to the `prices` table so historical values
accumulate and the portfolio endpoint always has a recent `last_price`.

Stops when the client disconnects (FastAPI `Request.is_disconnected()`).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Price
from app.db.session import AsyncSessionLocal

log = logging.getLogger(__name__)
router = APIRouter(tags=["prices"])

# Simulated baseline prices. Used as the centre of the random walk.
_BASELINES: dict[str, float] = {
    "AAPL": 192.50,
    "MSFT": 415.30,
    "NVDA": 740.10,
    "VOO": 510.75,
    "BND": 69.80,
    "USD": 1.00,
    "BTC": 65000.0,
}


def _seeded_price(symbol: str, second_bucket: int) -> float:
    """Deterministic synthetic price for `(symbol, second-bucket)`.

    Two callers asking at the same second see the same number. We hash to
    derive a stable "noise" in [-1, 1] then scale by the baseline volatility.
    """
    base = _BASELINES.get(symbol, 100.0)
    h = hashlib.sha256(f"{symbol}|{second_bucket}".encode()).hexdigest()
    # Take 6 hex chars → int → map to [-1, 1].
    noise_int = int(h[:6], 16)
    noise = (noise_int / 0xFFFFFF) * 2 - 1  # [-1, 1]

    # USD-style stablecoin: tiny jitter only.
    if symbol in {"USD", "USDX-MM"}:
        return round(1.0 + noise * 0.0005, 6)

    # ±0.5% intraday wiggle, plus a slow sine drift so the chart looks alive.
    drift = math.sin(second_bucket / 30.0) * 0.002
    return round(base * (1 + noise * 0.005 + drift), 4)


async def _persist_tick(symbol: str, ts: datetime, price: float) -> None:
    """Best-effort insert of one price row. ON CONFLICT no-op."""
    try:
        async with AsyncSessionLocal() as s:
            stmt = (
                pg_insert(Price)
                .values(symbol=symbol, ts=ts, price=Decimal(str(price)))
                .on_conflict_do_nothing(index_elements=["symbol", "ts"])
            )
            await s.execute(stmt)
            await s.commit()
    except Exception:  # pragma: no cover — never let persistence kill the stream
        log.exception("failed to persist tick for %s", symbol)


@router.get("/prices/stream")
async def prices_stream(
    request: Request,
    symbols: str = Query("AAPL,MSFT,NVDA,VOO,BND"),
    interval_ms: int = Query(500, ge=50, le=5000),
    persist_every: int = Query(4, ge=1, le=100),
    max_ticks: int = Query(0, ge=0, description="0 = stream until client disconnects"),
) -> StreamingResponse:
    """SSE stream of simulated prices for the given comma-separated symbols.

    `max_ticks` is primarily for tests — a positive value caps the number of
    iterations and lets the generator close cleanly without depending on the
    transport surfacing a disconnect.
    """
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    async def event_gen() -> AsyncIterator[str]:
        tick = 0
        while True:
            if max_ticks and tick >= max_ticks:
                return
            if await request.is_disconnected():
                log.debug("client disconnected; stopping price stream")
                return
            now = datetime.now(tz=timezone.utc)
            second_bucket = int(now.timestamp())
            for sym in sym_list:
                price = _seeded_price(sym, second_bucket)
                payload = {
                    "symbol": sym,
                    "price": price,
                    "ts": now.isoformat(),
                }
                yield f"data: {json.dumps(payload)}\n\n"

                # Persist every Nth tick per symbol so history accumulates.
                if tick % persist_every == 0:
                    await _persist_tick(sym, now, price)

            tick += 1
            await asyncio.sleep(interval_ms / 1000)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
