"""Turns one scrape run's per-listing results (app/scraping/pipeline.py::ScrapeStats) into
Notification rows — the "alert strictly after we've scraped new data" step called from
app/scraping/worker.py::run_scrape_job once a job finishes. See issues #21 (PRICE_DROP via
Follow) and #26 (NEW_MATCH via SavedSearch).
"""

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.listings.repository import FollowRepository
from app.models.listing import Listing
from app.models.notification import NotificationType
from app.models.saved_search import SavedSearch
from app.models.scrape_job import ScrapeJob
from app.notifications.service import NotificationService
from app.scraping.pipeline import ScrapeStats
from app.scraping.schemas import decode_job_query
from app.search.query import SearchQuery

EmailEnqueuer = Callable[[str], Awaitable[None]]


async def generate_notifications_for_job(
    session: AsyncSession,
    job: ScrapeJob,
    stats: ScrapeStats,
    enqueue_email: EmailEnqueuer | None = None,
) -> None:
    service = NotificationService(session, enqueue_email=enqueue_email)
    await _notify_price_drops(session, service, stats)
    await _notify_new_matches(session, service, job, stats)


async def _notify_price_drops(session: AsyncSession, service: NotificationService, stats: ScrapeStats) -> None:
    if not stats.price_drops:
        return
    follow_repository = FollowRepository(session)
    for listing_id, previous_price, current_price in stats.price_drops:
        listing = await session.get(Listing, listing_id)
        if listing is None:
            continue
        for follow in await follow_repository.list_followers(listing_id):
            await service.notify(
                follow.user_id,
                NotificationType.PRICE_DROP,
                {
                    "listing_title": listing.title,
                    "previous_price": previous_price,
                    "current_price": current_price,
                    "currency": listing.currency,
                },
                listing_id=listing_id,
            )


async def _find_matching_saved_searches(session: AsyncSession, query_hash: str) -> list[SavedSearch]:
    result = await session.execute(select(SavedSearch).where(SavedSearch.enabled.is_(True)))
    return [
        saved_search
        for saved_search in result.scalars().all()
        if SearchQuery.model_validate(saved_search.query).stable_hash() == query_hash
    ]


async def _notify_new_matches(
    session: AsyncSession, service: NotificationService, job: ScrapeJob, stats: ScrapeStats
) -> None:
    """One notification per (saved search, scrape run) — "N new listings for X" — not one per
    listing. Every new listing this run matched the same job query, which is exactly the saved
    search's query, so the count is the same for every saved search that matches it.
    """
    if not stats.new_listing_ids:
        return

    job_query, _ = decode_job_query(job.query)
    matching_saved_searches = await _find_matching_saved_searches(session, job_query.stable_hash())
    if not matching_saved_searches:
        return

    count = len(stats.new_listing_ids)
    for saved_search in matching_saved_searches:
        await service.notify(
            saved_search.user_id,
            NotificationType.NEW_MATCH,
            {
                "saved_search_id": str(saved_search.id),
                "saved_search_name": saved_search.name,
                "new_listings_count": count,
                "query_description": job_query.describe(),
            },
        )
