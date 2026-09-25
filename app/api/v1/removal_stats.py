from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.market.removal_schemas import Period, RemovalStatsResponse
from app.market.removal_service import RemovalStatsService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/removed-stats", response_model=RemovalStatsResponse)
async def get_removed_stats(
    response: Response,
    period: Period = "week",
    make: str | None = Query(default=None, max_length=64),
    session: AsyncSession = Depends(get_session),
) -> RemovalStatsResponse:
    # The rollup is rebuilt only twice a day, so a short shared cache costs nothing in freshness.
    response.headers["Cache-Control"] = "public, max-age=300"
    return await RemovalStatsService(session).get(period, make)
