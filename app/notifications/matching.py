"""Turns one scrape run's per-listing results (app/scraping/pipeline.py::ScrapeStats) into
Notification rows — the "alert strictly after we've scraped new data" step called from
app/scraping/worker.py::run_scrape_job once a job finishes. See issues #21 (PRICE_DROP via
Follow) and #26 (NEW_MATCH via SavedSearch).
"""

import uuid
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
from app.search.service import apply_filters

EmailEnqueuer = Callable[[str], Awaitable[None]]

# Cap on how many of this run's new listings ride along in a NEW_MATCH notification's payload —
# a saved search matching hundreds of new listings in one run shouldn't balloon every notification
# row; the UI shows "+N more" beyond this using new_listings_count, which always carries the full
# total.
_NEW_LISTINGS_PREVIEW_LIMIT = 5

# Keeps the `Listing.id IN (...)` list well under the DB driver's bind-parameter limit (32767 for
# asyncpg) — a FULL_SOURCE_REFRESH can touch far more listings than a saved-search crawl does.
_ID_FILTER_CHUNK_SIZE = 1000


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


async def _new_listings_preview(session: AsyncSession, listing_ids: list[uuid.UUID]) -> list[dict]:
    """Up to _NEW_LISTINGS_PREVIEW_LIMIT of this run's new listings, in enough detail for the UI
    to show *which* listings matched instead of just a count — a grouped NEW_MATCH notification
    otherwise gives no way to tell what actually changed.
    """
    preview_ids = listing_ids[:_NEW_LISTINGS_PREVIEW_LIMIT]
    if not preview_ids:
        return []
    result = await session.execute(select(Listing).where(Listing.id.in_(preview_ids)))
    listings_by_id = {listing.id: listing for listing in result.scalars().all()}
    return [
        {
            "id": str(listing.id),
            "title": listing.title,
            "price": listing.price,
            "currency": listing.currency,
        }
        for listing_id in preview_ids
        if (listing := listings_by_id.get(listing_id)) is not None
    ]


async def _listing_ids_matching_query(
    session: AsyncSession, listing_ids: list[uuid.UUID], query: SearchQuery
) -> list[uuid.UUID]:
    """The subset of `listing_ids` that satisfies every filter of `query`, in the original order.

    A scrape run only guarantees that what it saw matched whatever filters the *source adapter*
    could express in its search URL (e.g. PolovniAutomobiliSource.build_search_url ignores
    transmissions, interior_materials, equipment, ...) — so it can't be taken as proof that a
    listing matches the saved search. The DB filter is the same one the search page itself uses
    (app/search/service.py::apply_filters), so a notification only ever counts listings the user
    would actually see in that search.
    """
    matching: set[uuid.UUID] = set()
    for start in range(0, len(listing_ids), _ID_FILTER_CHUNK_SIZE):
        chunk = listing_ids[start : start + _ID_FILTER_CHUNK_SIZE]
        stmt = apply_filters(select(Listing.id).where(Listing.id.in_(chunk)), query)
        matching.update((await session.execute(stmt)).scalars().all())
    return [listing_id for listing_id in listing_ids if listing_id in matching]


async def _notify_new_matches(
    session: AsyncSession, service: NotificationService, job: ScrapeJob, stats: ScrapeStats
) -> None:
    """One notification per (saved search, scrape run) — "N new, M updated for X" — not one per
    listing. Saved searches are matched to the job by identical query (stable_hash), so the counts
    are the same for every saved search that matches it. They only count listings that actually
    satisfy that query, not everything the run happened to crawl (see _listing_ids_matching_query).
    """
    if not stats.new_listing_ids and not stats.updated_listing_ids:
        return

    job_query, _ = decode_job_query(job.query)
    matching_saved_searches = await _find_matching_saved_searches(session, job_query.stable_hash())
    if not matching_saved_searches:
        return

    new_listing_ids = await _listing_ids_matching_query(session, stats.new_listing_ids, job_query)
    updated_listing_ids = await _listing_ids_matching_query(session, stats.updated_listing_ids, job_query)
    if not new_listing_ids and not updated_listing_ids:
        return

    new_count = len(new_listing_ids)
    updated_count = len(updated_listing_ids)
    new_listings = await _new_listings_preview(session, new_listing_ids)
    for saved_search in matching_saved_searches:
        await service.notify(
            saved_search.user_id,
            NotificationType.NEW_MATCH,
            {
                "saved_search_id": str(saved_search.id),
                "saved_search_name": saved_search.name,
                "new_listings_count": new_count,
                "updated_listings_count": updated_count,
                "new_listings": new_listings,
                "query_description": job_query.describe(),
            },
        )
