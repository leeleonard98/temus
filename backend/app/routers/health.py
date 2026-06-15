"""Health check endpoint with DB connectivity probe."""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """Return service health and DB connectivity.

    200: {"status": "healthy", "db": "connected"}
    503: {"status": "degraded", "db": "disconnected"}
    """
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "db": "disconnected"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "healthy", "db": "connected"},
    )
