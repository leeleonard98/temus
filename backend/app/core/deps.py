"""FastAPI dependency injectables."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async DB session and close it after."""
    async with AsyncSessionLocal() as session:
        yield session
