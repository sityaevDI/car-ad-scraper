from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_csrf
from app.db.session import get_session
from app.market.config import get_market_config
from app.market.schemas import MarketConfigOut, MarketConfigUpdate
from app.models.user import User

# Threshold tuning is an admin action (mirrors /api/v1/scrape/rate-limit) — every route here sits
# behind require_admin, not get_current_user.
router = APIRouter(prefix="/market", tags=["market"])


@router.get("/config", response_model=MarketConfigOut)
async def get_config(
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
) -> MarketConfigOut:
    config = await get_market_config(session)
    await session.commit()
    return MarketConfigOut.model_validate(config)


@router.patch("/config", response_model=MarketConfigOut)
async def update_config(
    payload: MarketConfigUpdate,
    session: AsyncSession = Depends(get_session),
    _current_user: User = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
) -> MarketConfigOut:
    """Takes effect for every recompute after this call — app/market/service.py reads the current
    row fresh on each cron tick, so segments already mid-recompute aren't affected.
    """
    config = await get_market_config(session)
    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(config, field, value)
    await session.commit()
    return MarketConfigOut.model_validate(config)
