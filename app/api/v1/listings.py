import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.listings.repository import ListingRepository
from app.listings.schemas import ListingHistoryOut, ListingOut, ListingSnapshotOut

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ListingOut:
    listing = await ListingRepository(session).get_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingOut.model_validate(listing)


@router.get("/{listing_id}/history", response_model=ListingHistoryOut)
async def get_listing_history(
    listing_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ListingHistoryOut:
    repository = ListingRepository(session)
    listing = await repository.get_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    snapshots = await repository.get_history(listing_id)
    return ListingHistoryOut(
        listing=ListingOut.model_validate(listing),
        snapshots=[ListingSnapshotOut.model_validate(s) for s in snapshots],
    )
