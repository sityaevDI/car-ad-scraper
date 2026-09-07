from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.listing import Listing, ListingStatus

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/makes", response_model=dict[str, list[str]])
async def get_makes(session: AsyncSession = Depends(get_session)) -> dict[str, list[str]]:
    result = await session.execute(
        select(Listing.make, Listing.model).where(Listing.status == ListingStatus.ACTIVE).distinct()
    )
    makes: dict[str, list[str]] = {}
    for make, model in result.all():
        makes.setdefault(make, [])
        if model not in makes[make]:
            makes[make].append(model)
    return makes
