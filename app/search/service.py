"""Grouped/flat search over Listings. See docs/adr/06_SEARCH_MARKET.md.

Grouped results deliberately do *not* carry a market price/score — a user-chosen `group_by`
combination isn't the same thing as a market segment (app/market/segment.py), and conflating them
is a scope trap (see the plan behind #16/#18/#19). Flat (ungrouped) results *do* get a per-listing
price_score (app/market/service.py::estimate_for_listings), since each row there is a single real
listing with its own well-defined segment.
"""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.listings.schemas import ListingOut
from app.market.segment import ENGINE_VOLUME_BUCKET_SIZE
from app.market.service import MarketPriceService
from app.models.listing import Listing, ListingStatus
from app.search.query import SearchQuery, SearchRequest
from app.search.schemas import ListingGroupOut, SearchResponse

# Real listings report exact engine displacement (1968/1998/2000cc are all "2.0"), which would
# otherwise fragment one group into several near-duplicates — verified against live scrape data.
# Round to the nearest 100cc (app/market/segment.py::ENGINE_VOLUME_BUCKET_SIZE, shared so this and
# market segmentation never drift apart), which still keeps genuinely different engines apart (e.g.
# Škoda's 1.9 TDI at ~1896-1898cc buckets to 1900, separate from the 2.0 TDI bucket at 2000).
_ENGINE_VOLUME_BUCKET_HALF = ENGINE_VOLUME_BUCKET_SIZE // 2
_ENGINE_VOLUME_BUCKET = (
    ((Listing.engine_volume_cc + _ENGINE_VOLUME_BUCKET_HALF) // ENGINE_VOLUME_BUCKET_SIZE) * ENGINE_VOLUME_BUCKET_SIZE
).label("engine_volume_cc")

ALLOWED_GROUP_FIELDS = {
    "make": Listing.make,
    "model": Listing.model,
    "production_year": Listing.production_year,
    "fuel_type": Listing.fuel_type,
    "transmission": Listing.transmission,
    "engine_volume_cc": _ENGINE_VOLUME_BUCKET,
    "body_type": Listing.body_type,
    "interior_material": Listing.interior_material,
}

_FLAT_SORTS: dict[str, ColumnElement] = {
    "price_asc": Listing.price.asc(),
    "price_desc": Listing.price.desc(),
    "mileage_asc": Listing.mileage_km.asc(),
    "mileage_desc": Listing.mileage_km.desc(),
    "year_desc": Listing.production_year.desc(),
    "first_seen_desc": Listing.first_seen_at.desc(),
}


@dataclass
class _GroupRow:
    key: dict
    count: int
    price_min: int
    price_avg: float
    price_max: int
    year_min: int
    year_max: int
    mileage_min: int
    mileage_max: int


def _apply_filters(stmt: Select, query: SearchQuery) -> Select:
    stmt = stmt.where(Listing.status == ListingStatus.ACTIVE)
    if query.make:
        stmt = stmt.where(func.lower(Listing.make) == query.make.lower())
    if query.models:
        lowered = [m.lower() for m in query.models]
        stmt = stmt.where(func.lower(Listing.model).in_(lowered))
    if query.year_min is not None:
        stmt = stmt.where(Listing.production_year >= query.year_min)
    if query.year_max is not None:
        stmt = stmt.where(Listing.production_year <= query.year_max)
    if query.price_min is not None:
        stmt = stmt.where(Listing.price >= query.price_min)
    if query.price_max is not None:
        stmt = stmt.where(Listing.price <= query.price_max)
    if query.mileage_min is not None:
        stmt = stmt.where(Listing.mileage_km >= query.mileage_min)
    if query.mileage_max is not None:
        stmt = stmt.where(Listing.mileage_km <= query.mileage_max)
    if query.engine_volume_min is not None:
        stmt = stmt.where(Listing.engine_volume_cc >= query.engine_volume_min)
    if query.engine_volume_max is not None:
        stmt = stmt.where(Listing.engine_volume_cc <= query.engine_volume_max)
    if query.power_min is not None:
        stmt = stmt.where(Listing.power_hp >= query.power_min)
    if query.power_max is not None:
        stmt = stmt.where(Listing.power_hp <= query.power_max)
    if query.fuel_types:
        stmt = stmt.where(Listing.fuel_type.in_(query.fuel_types))
    if query.transmissions:
        stmt = stmt.where(Listing.transmission.in_(query.transmissions))
    if query.body_types:
        stmt = stmt.where(Listing.body_type.in_(query.body_types))
    if query.interior_materials:
        stmt = stmt.where(Listing.interior_material.in_(query.interior_materials))
    if query.air_conditions:
        stmt = stmt.where(Listing.air_condition.in_(query.air_conditions))
    if query.seats:
        stmt = stmt.where(Listing.seats.in_(query.seats))
    if query.equipment:
        stmt = stmt.where(Listing.equipment.contains(query.equipment))
    if query.location:
        stmt = stmt.where(func.lower(Listing.location) == query.location.lower())
    return stmt


def _build_label(group: dict) -> str:
    parts: list[str] = []
    if group.get("make"):
        parts.append(str(group["make"]))
    if group.get("model"):
        parts.append(str(group["model"]))
    if group.get("engine_volume_cc"):
        parts.append(f"{group['engine_volume_cc'] / 1000:.1f}L")
    if group.get("fuel_type"):
        parts.append(str(group["fuel_type"]).title())
    if group.get("transmission"):
        parts.append(str(group["transmission"]).title())
    if group.get("body_type"):
        parts.append(str(group["body_type"]).title())
    if group.get("interior_material"):
        parts.append(str(group["interior_material"]).title())
    if group.get("production_year"):
        parts.append(str(group["production_year"]))
    return " ".join(parts) if parts else "Other"


class SearchService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, request: SearchRequest) -> SearchResponse:
        if request.group_by:
            return await self._search_grouped(request)
        return await self._search_flat(request)

    async def _search_flat(self, request: SearchRequest) -> SearchResponse:
        base = _apply_filters(select(Listing), request.query)

        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        order = _FLAT_SORTS.get(request.sort, Listing.first_seen_at.desc())
        offset = (request.page - 1) * request.page_size
        stmt = base.order_by(order).offset(offset).limit(request.page_size)
        rows = (await self.session.execute(stmt)).scalars().all()

        price_scores = await MarketPriceService(self.session).get_price_scores(list(rows))
        listings = []
        for row in rows:
            listing_out = ListingOut.model_validate(row)
            listing_out.price_score = price_scores.get(row.id)
            listings.append(listing_out)

        return SearchResponse(
            listings=listings,
            total_listings=total,
            page=request.page,
            page_size=request.page_size,
        )

    async def _search_grouped(self, request: SearchRequest) -> SearchResponse:
        group_by = request.group_by
        assert group_by, "search() only calls _search_grouped when group_by is truthy"

        unknown = set(group_by) - ALLOWED_GROUP_FIELDS.keys()
        if unknown:
            raise HTTPException(status_code=400, detail=f"Invalid group_by fields: {sorted(unknown)}")

        group_columns = [ALLOWED_GROUP_FIELDS[field] for field in group_by]

        stmt = select(
            *group_columns,
            # Labeled "group_count", not "count" — Row already has a real `.count` (from tuple),
            # so attribute access on a "count"-labeled column would shadow it.
            func.count(Listing.id).label("group_count"),
            func.min(Listing.price).label("price_min"),
            func.avg(Listing.price).label("price_avg"),
            func.max(Listing.price).label("price_max"),
            func.min(Listing.production_year).label("year_min"),
            func.max(Listing.production_year).label("year_max"),
            func.min(Listing.mileage_km).label("mileage_min"),
            func.max(Listing.mileage_km).label("mileage_max"),
        )
        stmt = _apply_filters(stmt, request.query).group_by(*group_columns)
        if request.min_group_count is not None:
            stmt = stmt.having(func.count(Listing.id) >= request.min_group_count)

        if request.sort == "price_asc":
            stmt = stmt.order_by(func.min(Listing.price).asc())
        elif request.sort == "price_desc":
            stmt = stmt.order_by(func.max(Listing.price).desc())
        elif request.sort == "year_desc":
            stmt = stmt.order_by(func.max(Listing.production_year).desc())
        else:
            stmt = stmt.order_by(func.count(Listing.id).desc())

        # Group counts for one source/query are small (at most a few thousand distinct
        # make/model/engine/fuel/transmission combos) so paginating in Python after fetching all
        # groups is simpler than a second COUNT query — revisit if that stops being true.
        rows = (await self.session.execute(stmt)).all()
        total_groups = len(rows)

        offset = (request.page - 1) * request.page_size
        page_rows = rows[offset : offset + request.page_size]

        groups: list[ListingGroupOut] = []
        total_listings = 0
        for row in rows:
            total_listings += row.group_count
        for row in page_rows:
            group = {field: getattr(row, field) for field in group_by}
            groups.append(
                ListingGroupOut(
                    group=group,
                    label=_build_label(group),
                    count=row.group_count,
                    currency="EUR",
                    price_min=row.price_min,
                    price_avg=round(row.price_avg),
                    price_max=row.price_max,
                    year_min=row.year_min,
                    year_max=row.year_max,
                    mileage_min=row.mileage_min,
                    mileage_max=row.mileage_max,
                )
            )

        return SearchResponse(
            groups=groups,
            total_listings=total_listings,
            total_groups=total_groups,
            page=request.page,
            page_size=request.page_size,
        )
