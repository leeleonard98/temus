"""Integration tests for `scripts.seed_demo` — run twice = no duplicates."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, Goal, Position, User

pytestmark = pytest.mark.asyncio


async def test_seed_idempotent(async_session: AsyncSession, monkeypatch) -> None:
    # Point the seed script's session factory at the test container.
    from scripts import seed_demo as sd

    bind = async_session.bind

    class _Factory:
        def __call__(self):
            return _Ctx(bind)

    class _Ctx:
        def __init__(self, bind):
            self.bind = bind

        async def __aenter__(self):
            from sqlalchemy.ext.asyncio import async_sessionmaker
            self._sm = async_sessionmaker(self.bind, expire_on_commit=False)
            self._sess = self._sm()
            return self._sess

        async def __aexit__(self, exc_type, exc, tb):
            await self._sess.close()

    monkeypatch.setattr(sd, "AsyncSessionLocal", _Factory())

    s1 = await sd.seed()
    s2 = await sd.seed()
    assert s1 == s2

    # Sanity counts.
    n_users = await async_session.scalar(select(func.count()).select_from(User))
    n_accounts = await async_session.scalar(select(func.count()).select_from(Account))
    n_positions = await async_session.scalar(select(func.count()).select_from(Position))
    n_goals = await async_session.scalar(select(func.count()).select_from(Goal))

    assert n_users == 2  # client + advisor
    assert n_accounts == 4  # 3 client + 1 advisor
    # 3 client accounts hold 12 holdings (rows in _CLIENT_HOLDINGS) + 2 advisor.
    assert n_positions >= 12
    assert n_goals == 2
