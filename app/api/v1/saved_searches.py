import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_csrf
from app.db.session import get_session
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.saved_searches.repository import MAX_FREE_SAVED_SEARCHES, SavedSearchRepository
from app.saved_searches.schemas import SavedSearchCreate, SavedSearchOut, SavedSearchUpdate
from app.search.query import SearchQuery, SearchRequest
from app.search.schemas import SearchResponse
from app.search.service import SearchService

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


@router.get("", response_model=list[SavedSearchOut])
async def list_saved_searches(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SavedSearchOut]:
    rows = await SavedSearchRepository(session).list_for_user(current_user.id)
    return [SavedSearchOut.model_validate(row) for row in rows]


@router.post("", response_model=SavedSearchOut, status_code=201)
async def create_saved_search(
    payload: SavedSearchCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> SavedSearchOut:
    repo = SavedSearchRepository(session)
    count = await repo.count_for_user(current_user.id)
    if count >= MAX_FREE_SAVED_SEARCHES:
        raise HTTPException(status_code=402, detail=f"Saved search limit reached ({MAX_FREE_SAVED_SEARCHES})")

    saved_search = SavedSearch(
        user_id=current_user.id,
        name=payload.name,
        query=payload.query.model_dump(),
        notification_settings=payload.notification_settings,
    )
    session.add(saved_search)
    await session.commit()
    return SavedSearchOut.model_validate(saved_search)


@router.get("/{saved_search_id}", response_model=SavedSearchOut)
async def get_saved_search(
    saved_search_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SavedSearchOut:
    saved_search = await SavedSearchRepository(session).get_owned(saved_search_id, current_user.id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return SavedSearchOut.model_validate(saved_search)


@router.patch("/{saved_search_id}", response_model=SavedSearchOut)
async def update_saved_search(
    saved_search_id: uuid.UUID,
    payload: SavedSearchUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> SavedSearchOut:
    saved_search = await SavedSearchRepository(session).get_owned(saved_search_id, current_user.id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    if payload.name is not None:
        saved_search.name = payload.name
    if payload.query is not None:
        saved_search.query = payload.query.model_dump()
    if payload.enabled is not None:
        saved_search.enabled = payload.enabled
    if payload.notification_settings is not None:
        saved_search.notification_settings = payload.notification_settings
    await session.commit()
    return SavedSearchOut.model_validate(saved_search)


@router.delete("/{saved_search_id}", status_code=204)
async def delete_saved_search(
    saved_search_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> None:
    saved_search = await SavedSearchRepository(session).get_owned(saved_search_id, current_user.id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    await session.delete(saved_search)
    await session.commit()


@router.post("/{saved_search_id}/run", response_model=SearchResponse)
async def run_saved_search(
    saved_search_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
) -> SearchResponse:
    """Runs the saved query against whatever is currently in the DB — a live view, not a fresh
    scrape. Periodic background refresh of the underlying data is app/scraping/scheduler.py (#26).
    """
    saved_search = await SavedSearchRepository(session).get_owned(saved_search_id, current_user.id)
    if saved_search is None:
        raise HTTPException(status_code=404, detail="Saved search not found")

    query = SearchQuery.model_validate(saved_search.query)
    result = await SearchService(session).search(SearchRequest(query=query))

    saved_search.last_run_at = datetime.now(timezone.utc)
    await session.commit()
    return result
