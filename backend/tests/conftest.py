"""Shared pytest fixtures: postgres container, async session, FastAPI client."""
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.deps import get_session
from app.main import app


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start a Postgres 16 container for the whole test session.

    Applies all alembic migrations once at startup.
    """
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        sync_url = pg.get_connection_url()
        # testcontainers returns postgresql+psycopg2:// or postgresql://
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
        if async_url.startswith("postgresql://"):
            async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Run alembic against a sync URL (psycopg).
        sync_psycopg_url = async_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg://"
        )
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_psycopg_url)
        command.upgrade(alembic_cfg, "head")

        pg.async_url = async_url  # type: ignore[attr-defined]
        yield pg


@pytest_asyncio.fixture
async def async_session(
    postgres_container: PostgresContainer,
) -> AsyncIterator[AsyncSession]:
    """Provide a clean async session per test.

    Truncates app tables before each test so commits made by FastAPI route
    handlers don't leak between tests. (Per-test rollback alone is not enough
    because routes call `session.commit()` themselves.)
    """
    engine = create_async_engine(
        postgres_container.async_url,  # type: ignore[attr-defined]
        future=True,
    )
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        # Wipe between tests. RESTART IDENTITY isn't strictly needed (uuid pk)
        # but CASCADE clears FK-linked rows.
        await session.execute(
            text(
                "TRUNCATE TABLE "
                "chat_messages, chat_sessions, "
                "positions, accounts, goals, prices, "
                "users "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Async HTTP client with `get_session` overridden to the test session."""

    async def _override() -> AsyncIterator[AsyncSession]:
        yield async_session

    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
