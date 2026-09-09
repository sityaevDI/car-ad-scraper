"""Endpoint-level tests for the saved-search API, following tests/unit/test_scrape_endpoints.py's
pattern: real FastAPI app over ASGI, dependency overrides instead of a real Postgres/Redis/arq.
"""

from datetime import datetime, timezone

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
    client: AsyncClient, email_sender: RecordingEmailSender, email: str = "saver@example.com"
) -> None:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter2pass"})
    token = email_sender.last_token()
    await client.post("/api/v1/auth/verify-email", json={"token": token})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})


async def test_create_saved_search(client, email_sender):
    await _register_and_login(client, email_sender)

    response = await client.post(
        "/api/v1/saved-searches",
        json={"name": "Skoda Octavia", "query": {"make": "Skoda"}},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Skoda Octavia"
    assert body["query"]["make"] == "Skoda"
    assert body["enabled"] is True
    assert body["last_run_at"] is None


async def test_create_saved_search_requires_auth(client):
    response = await client.post("/api/v1/saved-searches", json={"name": "x", "query": {}})
    assert response.status_code == 401


async def test_create_saved_search_enforces_free_plan_limit(client, email_sender):
    await _register_and_login(client, email_sender)

    for i in range(5):
        response = await client.post(
            "/api/v1/saved-searches",
            json={"name": f"Search {i}", "query": {}},
            headers=_csrf_headers(client),
        )
        assert response.status_code == 201

    response = await client.post(
        "/api/v1/saved-searches", json={"name": "One too many", "query": {}}, headers=_csrf_headers(client)
    )
    assert response.status_code == 402


async def test_list_saved_searches_only_returns_own(client, email_sender):
    await _register_and_login(client, email_sender, email="alice@example.com")
    await client.post(
        "/api/v1/saved-searches", json={"name": "Alice's search", "query": {}}, headers=_csrf_headers(client)
    )
    await client.post("/api/v1/auth/logout")

    await _register_and_login(client, email_sender, email="bob@example.com")
    await client.post(
        "/api/v1/saved-searches", json={"name": "Bob's search", "query": {}}, headers=_csrf_headers(client)
    )

    response = await client.get("/api/v1/saved-searches")

    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert names == ["Bob's search"]


async def test_get_saved_search_404_for_other_users_search(client, email_sender):
    await _register_and_login(client, email_sender, email="alice@example.com")
    create_response = await client.post(
        "/api/v1/saved-searches", json={"name": "Alice's search", "query": {}}, headers=_csrf_headers(client)
    )
    saved_search_id = create_response.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register_and_login(client, email_sender, email="bob@example.com")
    response = await client.get(f"/api/v1/saved-searches/{saved_search_id}")

    assert response.status_code == 404


async def test_update_saved_search(client, email_sender):
    await _register_and_login(client, email_sender)
    create_response = await client.post(
        "/api/v1/saved-searches", json={"name": "Skoda", "query": {"make": "Skoda"}}, headers=_csrf_headers(client)
    )
    saved_search_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/v1/saved-searches/{saved_search_id}",
        json={"enabled": False, "name": "Skoda (paused)"},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["name"] == "Skoda (paused)"


async def test_delete_saved_search(client, email_sender):
    await _register_and_login(client, email_sender)
    create_response = await client.post(
        "/api/v1/saved-searches", json={"name": "Skoda", "query": {}}, headers=_csrf_headers(client)
    )
    saved_search_id = create_response.json()["id"]

    response = await client.delete(f"/api/v1/saved-searches/{saved_search_id}", headers=_csrf_headers(client))
    assert response.status_code == 204

    list_response = await client.get("/api/v1/saved-searches")
    assert list_response.json() == []


async def test_run_saved_search_returns_matching_listings_and_sets_last_run_at(
    client, email_sender, session_factory
):
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        source = Source(code="polovniautomobili", name="Polovni Automobili", domain="x.rs", country="RS")
        session.add(source)
        await session.flush()
        session.add(
            Listing(
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
        )
        await session.commit()

    await _register_and_login(client, email_sender)
    create_response = await client.post(
        "/api/v1/saved-searches", json={"name": "Skoda", "query": {"make": "Skoda"}}, headers=_csrf_headers(client)
    )
    saved_search_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/saved-searches/{saved_search_id}/run", headers=_csrf_headers(client))

    assert response.status_code == 200
    assert response.json()["total_listings"] == 1

    get_response = await client.get(f"/api/v1/saved-searches/{saved_search_id}")
    assert get_response.json()["last_run_at"] is not None
