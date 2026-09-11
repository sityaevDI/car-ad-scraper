import uuid
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saved_search import SavedSearch

# Stub free-plan limit — real per-plan enforcement (SubscriptionPlan.max_saved_searches) is
# Phase 5 billing (issues #43-47), not wired up yet.
MAX_FREE_SAVED_SEARCHES = 5


class SavedSearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[SavedSearch]:
        result = await self.session.execute(
            select(SavedSearch).where(SavedSearch.user_id == user_id).order_by(SavedSearch.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_owned(self, saved_search_id: uuid.UUID, user_id: uuid.UUID) -> SavedSearch | None:
        result = await self.session.execute(
            select(SavedSearch).where(SavedSearch.id == saved_search_id, SavedSearch.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)
        )
        return result.scalar_one()

    async def existing_ids(self, ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Which of `ids` still exist — lets callers tell a stale reference (e.g. a NEW_MATCH
        notification's payload.saved_search_id, kept as plain JSON rather than a FK) from a live one.
        """
        if not ids:
            return set()
        result = await self.session.execute(select(SavedSearch.id).where(SavedSearch.id.in_(ids)))
        return set(result.scalars().all())

    async def list_due(self, cutoff: datetime) -> list[SavedSearch]:
        """Enabled saved searches never refreshed, or last refreshed before `cutoff` — backs the
        periodic-refresh cron in app/scraping/scheduler.py (#26).
        """
        result = await self.session.execute(
            select(SavedSearch).where(
                SavedSearch.enabled.is_(True),
                or_(SavedSearch.last_run_at.is_(None), SavedSearch.last_run_at <= cutoff),
            )
        )
        return list(result.scalars().all())
