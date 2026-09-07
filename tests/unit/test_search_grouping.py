import pytest

from app.search.query import SearchQuery, SearchRequest
from app.search.service import SearchService
from tests.conftest import make_listing, seed_source

pytestmark = pytest.mark.asyncio


async def test_groups_by_make_model_engine_fuel_transmission(session):
    source = await seed_source(session)

    # 32 Octavia 2.0 TDI automatic, price/year/mileage spread
    session.add(make_listing(source.id, price=11_900, production_year=2017, mileage_km=240_000))
    session.add(make_listing(source.id, price=15_400, production_year=2021, mileage_km=110_000))
    session.add(make_listing(source.id, price=13_500, production_year=2019, mileage_km=180_000))

    # A different variant of the same model (manual gearbox) must be a separate group
    session.add(
        make_listing(source.id, price=9_000, production_year=2016, mileage_km=250_000, transmission="manual")
    )

    # A different make entirely
    session.add(
        make_listing(
            source.id,
            make="BMW",
            model="320d",
            price=13_200,
            production_year=2018,
            mileage_km=200_000,
            engine_volume_cc=1995,
        )
    )
    await session.commit()

    response = await SearchService(session).search(SearchRequest())

    assert response.total_listings == 5
    assert response.total_groups == 3
    groups_by_label = {g.label: g for g in response.groups}

    octavia = groups_by_label["Škoda Octavia 2.0L Diesel Automatic"]
    assert octavia.count == 3
    assert octavia.price_min == 11_900
    assert octavia.price_max == 15_400
    assert octavia.year_min == 2017
    assert octavia.year_max == 2021
    assert octavia.mileage_min == 110_000
    assert octavia.mileage_max == 240_000

    octavia_manual = groups_by_label["Škoda Octavia 2.0L Diesel Manual"]
    assert octavia_manual.count == 1

    bmw = groups_by_label["BMW 320d 2.0L Diesel Automatic"]
    assert bmw.count == 1

    # Groups ordered by count desc by default, so the 3-listing group comes first
    assert response.groups[0].label == "Škoda Octavia 2.0L Diesel Automatic"


async def test_filters_apply_before_grouping(session):
    source = await seed_source(session)
    session.add(make_listing(source.id, price=11_000, production_year=2017))
    session.add(make_listing(source.id, price=20_000, production_year=2021))
    await session.commit()

    request = SearchRequest(query=SearchQuery(price_max=15_000))
    response = await SearchService(session).search(request)

    assert response.total_listings == 1
    assert response.groups[0].price_max == 11_000


async def test_flat_mode_returns_listings_when_group_by_empty(session):
    source = await seed_source(session)
    session.add(make_listing(source.id, price=11_000))
    session.add(make_listing(source.id, price=20_000))
    await session.commit()

    request = SearchRequest(group_by=[], sort="price_asc")
    response = await SearchService(session).search(request)

    assert response.groups is None
    assert response.total_listings == 2
    assert [listing.price for listing in response.listings] == [11_000, 20_000]


async def test_invalid_group_by_field_rejected(session):
    from fastapi import HTTPException

    request = SearchRequest(group_by=["not_a_real_field"])
    with pytest.raises(HTTPException):
        await SearchService(session).search(request)
