import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional, require_csrf
from app.db.session import get_session
from app.listings.repository import FollowRepository, ListingRepository
from app.listings.schemas import ListingHistoryOut, ListingOut, ListingSnapshotOut
from app.models.listing import Listing
from app.models.user import User

router = APIRouter(prefix="/listings", tags=["listings"])


async def _to_listing_out(listing: Listing, current_user: User | None, session: AsyncSession) -> ListingOut:
    out = ListingOut.model_validate(listing)
    if current_user is not None:
        out.is_following = await FollowRepository(session).get(current_user.id, listing.id) is not None
    return out


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(
    listing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> ListingOut:
    listing = await ListingRepository(session).get_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return await _to_listing_out(listing, current_user, session)


@router.post("/{listing_id}/follow", status_code=204)
async def follow_listing(
    listing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> None:
    listing = await ListingRepository(session).get_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    await FollowRepository(session).follow(current_user.id, listing_id)
    await session.commit()


@router.delete("/{listing_id}/follow", status_code=204)
async def unfollow_listing(
    listing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> None:
    await FollowRepository(session).unfollow(current_user.id, listing_id)
    await session.commit()


@router.get("/{listing_id}/history", response_model=ListingHistoryOut)
async def get_listing_history(
    listing_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> ListingHistoryOut:
    repository = ListingRepository(session)
    listing = await repository.get_by_id(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    snapshots = await repository.get_history(listing_id)
    return ListingHistoryOut(
        listing=await _to_listing_out(listing, current_user, session),
        snapshots=[ListingSnapshotOut.model_validate(s) for s in snapshots],
    )
