import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.listing import Listing, ListingStatus
from app.models.snapshot import ListingSnapshot
from app.sources.base import SourceListing


def _description_hash(raw: dict) -> str | None:
    description = raw.get("description")
    if not description:
        return None
    return hashlib.sha256(description.encode("utf-8")).hexdigest()


class ListingRepository:
    """Owns Listing/ListingSnapshot persistence. Upserts by (source_id, external_id); always
    appends a new snapshot instead of overwriting history — see
    agent_documents/17_AGENT_INSTRUCTIONS.md "Never overwrite historical snapshots".
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, listing_id: uuid.UUID) -> Listing | None:
        return await self.session.get(Listing, listing_id)

    async def get_history(self, listing_id: uuid.UUID) -> list[ListingSnapshot]:
        result = await self.session.execute(
            select(ListingSnapshot)
            .where(ListingSnapshot.listing_id == listing_id)
            .order_by(ListingSnapshot.captured_at.asc())
        )
        return list(result.scalars().all())

    async def _find_existing(self, source_id: uuid.UUID, external_id: str) -> Listing | None:
        result = await self.session.execute(
            select(Listing).where(Listing.source_id == source_id, Listing.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def upsert_listing(self, source_id: uuid.UUID, data: SourceListing) -> tuple[Listing, bool]:
        """Insert a new Listing + its first Snapshot, or refresh an existing one and append a new
        Snapshot only if price/mileage/title actually changed. Returns (listing, is_new).
        """
        now = datetime.now(timezone.utc)
        existing = await self._find_existing(source_id, data.external_id)

        if existing is None:
            listing = Listing(
                source_id=source_id,
                external_id=data.external_id,
                canonical_url=data.canonical_url,
                title=data.title,
                make=data.make,
                model=data.model,
                production_year=data.production_year,
                mileage_km=data.mileage_km,
                price=data.price,
                currency=data.currency,
                fuel_type=data.fuel_type,
                transmission=data.transmission,
                body_type=data.body_type,
                engine_volume_cc=data.engine_volume_cc,
                power_hp=data.power_hp,
                location=data.location,
                seller_type=data.seller_type,
                image_url=data.image_url,
                status=ListingStatus.ACTIVE,
                first_seen_at=now,
                last_seen_at=now,
                last_checked_at=now,
            )
            self.session.add(listing)
            await self.session.flush()
            self._add_snapshot(listing, data, now)
            return listing, True

        existing.last_seen_at = now
        existing.last_checked_at = now
        existing.status = ListingStatus.ACTIVE
        existing.image_url = data.image_url

        changed = (
            existing.price != data.price
            or existing.mileage_km != data.mileage_km
            or existing.title != data.title
        )
        if changed:
            existing.price = data.price
            existing.mileage_km = data.mileage_km
            existing.title = data.title
            self._add_snapshot(existing, data, now)

        return existing, False

    async def mark_missing_as_removed(self, source_id: uuid.UUID, seen_external_ids: set[str]) -> int:
        """Mark active listings for a source that were not encountered in the latest crawl as
        removed. Never deletes rows — see agent_documents/17_AGENT_INSTRUCTIONS.md.

        Only correct for a full-source crawl. Not called from `scraping/pipeline.py` yet, since
        that pipeline runs one filtered SearchQuery at a time — calling this against a partial
        result set would wrongly mark every listing outside that filter as removed. Wire it up
        once a FULL_SOURCE_REFRESH job type is actually implemented.
        """
        result = await self.session.execute(
            select(Listing).where(Listing.source_id == source_id, Listing.status == ListingStatus.ACTIVE)
        )
        count = 0
        for listing in result.scalars().all():
            if listing.external_id not in seen_external_ids:
                listing.status = ListingStatus.REMOVED
                count += 1
        return count

    def _add_snapshot(self, listing: Listing, data: SourceListing, captured_at: datetime) -> None:
        self.session.add(
            ListingSnapshot(
                listing_id=listing.id,
                captured_at=captured_at,
                price=data.price,
                mileage_km=data.mileage_km,
                title=data.title,
                description_hash=_description_hash(data.raw),
                raw_payload=data.raw,
            )
        )
