from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.search.query import SearchRequest
from app.search.schemas import SearchResponse
from app.search.service import SearchService

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, session: AsyncSession = Depends(get_session)) -> SearchResponse:
    return await SearchService(session).search(request)
