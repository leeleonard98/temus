"""Integration tests for /api/v1/health.

Three patterns to template tomorrow's feature tests:
1) shape — request/response/JSON
2) DB-touching — exercises the real session
3) failure mode — dependency override forces an error
"""
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.deps import get_session
from app.main import app

pytestmark = pytest.mark.asyncio


async def test_health_returns_200_and_documented_schema(client: AsyncClient) -> None:
    """Healthy app returns 200 with the documented JSON shape."""
    # Act
    response = await client.get("/api/v1/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "db": "connected"}


async def test_health_db_check_actually_hits_the_database(
    client: AsyncClient,
) -> None:
    """The endpoint runs SELECT 1 against the real test DB.

    Asserts the DB-touching path works end-to-end via the test session.
    """
    # Act
    response = await client.get("/api/v1/health")

    # Assert
    assert response.status_code == 200
    assert response.json()["db"] == "connected"


async def test_health_returns_503_when_db_session_raises_operational_error() -> None:
    """When the DB layer raises OperationalError, endpoint reports degraded."""

    class _BadSession:
        async def execute(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise OperationalError("boom", None, Exception("db down"))

    async def _override() -> AsyncIterator[_BadSession]:
        yield _BadSession()

    # Arrange
    app.dependency_overrides[get_session] = _override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as bad_client:
            # Act
            response = await bad_client.get("/api/v1/health")

        # Assert
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "disconnected"}
    finally:
        app.dependency_overrides.clear()
