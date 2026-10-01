"""Endpoint-level tests for the listing follow API (#21), following
tests/unit/test_scrape_endpoints.py's pattern.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.email import get_email_sender
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.infrastructure.redis import get_redis
from app.main import app
from app.models.listing import Listing, ListingStatus
from app.models.snapshot import ListingSnapshot
from app.models.source import Source


class RecordingEmailSender:
    def __init__(self):
        self.sent = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_token(self) -> str:
        return self.sent[-1]["body"].rsplit("token=", 1)[-1]


@pytest.fixture
def email_sender():
    return RecordingEmailSender()


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory, email_sender):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    fake_redis = FakeAsyncRedis(decode_responses=True)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_email_sender] = lambda: email_sender

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    settings = get_settings()
    return {settings.csrf_header_name: client.cookies[settings.csrf_cookie_name]}


async def _register_and_login(
    client: AsyncClient, email_sender: RecordingEmailSender, email: str = "follower@example.com"
) -> None:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter2pass"})
    token = email_sender.last_token()
    await client.post("/api/v1/auth/verify-email", json={"token": token})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})


async def _seed_listing(session_factory) -> str:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        source = Source(code="polovniautomobili", name="Polovni Automobili", domain="x.rs", country="RS")
        session.add(source)
        await session.flush()
        listing = Listing(
            source_id=source.id,
            external_id="1",
            canonical_url="https://x.rs/1",
            title="Skoda Octavia",
            make="Skoda",
            model="Octavia",
            production_year=2019,
            mileage_km=100_000,
            price=10_000,
            currency="EUR",
            status=ListingStatus.ACTIVE,
            first_seen_at=now,
            last_seen_at=now,
            last_checked_at=now,
        )
        session.add(listing)
        await session.commit()
        return str(listing.id)


async def test_get_listing_without_auth_has_is_following_false(client, session_factory):
    listing_id = await _seed_listing(session_factory)
    response = await client.get(f"/api/v1/listings/{listing_id}")
    assert response.status_code == 200
    assert response.json()["is_following"] is False


async def test_follow_then_get_listing_reflects_is_following(client, email_sender, session_factory):
    listing_id = await _seed_listing(session_factory)
    await _register_and_login(client, email_sender)

    follow_response = await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    assert follow_response.status_code == 204

    response = await client.get(f"/api/v1/listings/{listing_id}")
    assert response.json()["is_following"] is True


async def test_follow_then_get_listing_history_reflects_is_following(client, email_sender, session_factory):
    # ListingDetailPage.tsx renders off /history, not the plain listing GET — both must carry
    # is_following, not just one of them.
    listing_id = await _seed_listing(session_factory)
    await _register_and_login(client, email_sender)

    await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))

    response = await client.get(f"/api/v1/listings/{listing_id}/history")
    assert response.json()["listing"]["is_following"] is True


async def test_follow_is_idempotent(client, email_sender, session_factory):
    listing_id = await _seed_listing(session_factory)
    await _register_and_login(client, email_sender)

    first = await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    second = await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    assert first.status_code == 204
    assert second.status_code == 204


async def test_unfollow_removes_follow(client, email_sender, session_factory):
    listing_id = await _seed_listing(session_factory)
    await _register_and_login(client, email_sender)
    await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))

    response = await client.delete(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/listings/{listing_id}")
    assert get_response.json()["is_following"] is False


async def test_unfollow_without_existing_follow_is_a_noop(client, email_sender, session_factory):
    listing_id = await _seed_listing(session_factory)
    await _register_and_login(client, email_sender)

    response = await client.delete(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    assert response.status_code == 204


async def test_follow_requires_auth(client, session_factory):
    listing_id = await _seed_listing(session_factory)
    response = await client.post(f"/api/v1/listings/{listing_id}/follow")
    assert response.status_code == 401


async def test_follow_unknown_listing_404s(client, email_sender):
    await _register_and_login(client, email_sender)
    response = await client.post(
        "/api/v1/listings/00000000-0000-0000-0000-000000000000/follow", headers=_csrf_headers(client)
    )
    assert response.status_code == 404


async def _seed_listings(session_factory, count: int, status: ListingStatus = ListingStatus.ACTIVE) -> list[str]:
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        source = Source(code="polovniautomobili", name="Polovni Automobili", domain="x.rs", country="RS")
        session.add(source)
        await session.flush()
        listings = [
            Listing(
                source_id=source.id,
                external_id=str(i),
                canonical_url=f"https://x.rs/{i}",
                title=f"Listing {i}",
                make="Skoda",
                model="Octavia",
                production_year=2019,
                mileage_km=100_000,
                price=10_000,
                currency="EUR",
                status=status,
                first_seen_at=now,
                last_seen_at=now,
                last_checked_at=now,
            )
            for i in range(count)
        ]
        session.add_all(listings)
        await session.commit()
        return [str(listing.id) for listing in listings]


async def test_list_followed_listings_requires_auth(client):
    response = await client.get("/api/v1/listings/following")
    assert response.status_code == 401


async def test_list_followed_listings_is_empty_without_follows(client, email_sender):
    await _register_and_login(client, email_sender)
    response = await client.get("/api/v1/listings/following")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


async def test_list_followed_listings_returns_newest_follow_first_and_only_own(
    client, email_sender, session_factory
):
    first, second, unfollowed = await _seed_listings(session_factory, 3)
    await _register_and_login(client, email_sender)
    await client.post(f"/api/v1/listings/{first}/follow", headers=_csrf_headers(client))
    await client.post(f"/api/v1/listings/{second}/follow", headers=_csrf_headers(client))
    await client.post("/api/v1/auth/logout", headers=_csrf_headers(client))

    # Another user's follow of a third listing must not leak into the first user's list.
    await _register_and_login(client, email_sender, email="other@example.com")
    await client.post(f"/api/v1/listings/{unfollowed}/follow", headers=_csrf_headers(client))
    await client.post("/api/v1/auth/logout", headers=_csrf_headers(client))

    await _register_and_login(client, email_sender, email="follower@example.com")
    response = await client.get("/api/v1/listings/following")
    body = response.json()
    assert body["total"] == 2
    assert [item["listing"]["id"] for item in body["items"]] == [second, first]
    assert all(item["listing"]["is_following"] is True for item in body["items"])


async def test_list_followed_listings_includes_removed_listings(client, email_sender, session_factory):
    (listing_id,) = await _seed_listings(session_factory, 1, status=ListingStatus.REMOVED)
    await _register_and_login(client, email_sender)
    await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))

    body = (await client.get("/api/v1/listings/following")).json()
    assert [item["listing"]["status"] for item in body["items"]] == ["removed"]


async def test_list_followed_listings_price_at_follow_ignores_later_snapshots(
    client, email_sender, session_factory
):
    (listing_id,) = await _seed_listings(session_factory, 1)
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        for captured_at, price in [(now - timedelta(days=5), 12_000), (now - timedelta(days=2), 11_000)]:
            session.add(
                ListingSnapshot(
                    listing_id=uuid.UUID(listing_id), captured_at=captured_at, price=price, mileage_km=1, title="t"
                )
            )
        await session.commit()
    await _register_and_login(client, email_sender)
    await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))
    # A price drop after the follow — this is the "current" price, not the price at follow time.
    async with session_factory() as session:
        session.add(
            ListingSnapshot(
                listing_id=uuid.UUID(listing_id),
                captured_at=now + timedelta(hours=1),
                price=9_000,
                mileage_km=1,
                title="t",
            )
        )
        await session.commit()

    (item,) = (await client.get("/api/v1/listings/following")).json()["items"]
    assert item["price_at_follow"] == 11_000
    assert item["listing"]["price"] == 10_000


async def test_list_followed_listings_paginates(client, email_sender, session_factory):
    listing_ids = await _seed_listings(session_factory, 3)
    await _register_and_login(client, email_sender)
    for listing_id in listing_ids:
        await client.post(f"/api/v1/listings/{listing_id}/follow", headers=_csrf_headers(client))

    response = await client.get("/api/v1/listings/following", params={"page": 2, "page_size": 2})
    body = response.json()
    assert body["total"] == 3
    assert (body["page"], body["page_size"]) == (2, 2)
    assert [item["listing"]["id"] for item in body["items"]] == [listing_ids[0]]
