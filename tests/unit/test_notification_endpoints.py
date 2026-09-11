"""Endpoint-level tests for the in-app notification API (#23)."""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.email import get_email_sender
from app.auth.repository import UserRepository
from app.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.infrastructure.redis import get_redis
from app.main import app
from app.models.notification import Notification, NotificationType


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
    client: AsyncClient, email_sender: RecordingEmailSender, email: str = "notified@example.com"
) -> None:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter2pass"})
    token = email_sender.last_token()
    await client.post("/api/v1/auth/verify-email", json={"token": token})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})


async def _seed_notification(session_factory, email: str, **overrides) -> str:
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        defaults = dict(user_id=user.id, type=NotificationType.NEW_MATCH, payload={"listing_title": "Skoda Octavia"})
        defaults.update(overrides)
        notification = Notification(**defaults)
        session.add(notification)
        await session.commit()
        return str(notification.id)


async def test_list_notifications_returns_own_with_unread_count(client, email_sender, session_factory):
    await _register_and_login(client, email_sender)
    await _seed_notification(session_factory, "notified@example.com")
    await _seed_notification(session_factory, "notified@example.com")

    response = await client.get("/api/v1/me/notifications")

    assert response.status_code == 200
    body = response.json()
    assert len(body["notifications"]) == 2
    assert body["unread_count"] == 2


async def test_list_notifications_requires_auth(client):
    response = await client.get("/api/v1/me/notifications")
    assert response.status_code == 401


async def test_list_notifications_only_returns_own(client, email_sender, session_factory):
    await _register_and_login(client, email_sender, email="alice@example.com")
    await _seed_notification(session_factory, "alice@example.com")
    await client.post("/api/v1/auth/logout")

    await _register_and_login(client, email_sender, email="bob@example.com")
    response = await client.get("/api/v1/me/notifications")

    assert response.status_code == 200
    assert response.json()["notifications"] == []


async def test_mark_notification_read(client, email_sender, session_factory):
    await _register_and_login(client, email_sender)
    notification_id = await _seed_notification(session_factory, "notified@example.com")

    response = await client.post(f"/api/v1/me/notifications/{notification_id}/read", headers=_csrf_headers(client))

    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    list_response = await client.get("/api/v1/me/notifications")
    assert list_response.json()["unread_count"] == 0


async def test_mark_notification_read_404_for_other_users_notification(client, email_sender, session_factory):
    await _register_and_login(client, email_sender, email="alice@example.com")
    notification_id = await _seed_notification(session_factory, "alice@example.com")
    await client.post("/api/v1/auth/logout")

    await _register_and_login(client, email_sender, email="bob@example.com")
    response = await client.post(f"/api/v1/me/notifications/{notification_id}/read", headers=_csrf_headers(client))

    assert response.status_code == 404


async def test_opening_new_match_notification_after_saved_search_deleted(client, email_sender, session_factory):
    """Saved search deleted, matched notification survives, flagged so the UI won't link to it —
    the notification stays visible and markable-as-read, but is flagged with saved_search_deleted
    so the UI knows not to render a (dead) link, and the underlying saved search still 404s directly.
    """
    await _register_and_login(client, email_sender)

    create_response = await client.post(
        "/api/v1/saved-searches",
        json={"name": "Skoda alert", "query": {"make": "skoda"}},
        headers=_csrf_headers(client),
    )
    assert create_response.status_code == 201
    saved_search_id = create_response.json()["id"]

    notification_id = await _seed_notification(
        session_factory,
        "notified@example.com",
        payload={
            "saved_search_id": saved_search_id,
            "saved_search_name": "Skoda alert",
            "new_listings_count": 3,
            "updated_listings_count": 0,
            "query_description": "Skoda",
        },
    )

    delete_response = await client.delete(f"/api/v1/saved-searches/{saved_search_id}", headers=_csrf_headers(client))
    assert delete_response.status_code == 204

    list_response = await client.get("/api/v1/me/notifications")
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body["notifications"]) == 1
    assert body["notifications"][0]["payload"]["saved_search_id"] == saved_search_id
    assert body["notifications"][0]["saved_search_deleted"] is True

    read_response = await client.post(f"/api/v1/me/notifications/{notification_id}/read", headers=_csrf_headers(client))
    assert read_response.status_code == 200
    assert read_response.json()["saved_search_deleted"] is True

    open_response = await client.get(f"/api/v1/saved-searches/{saved_search_id}")
    assert open_response.status_code == 404


async def test_new_match_notification_not_flagged_while_saved_search_exists(client, email_sender, session_factory):
    await _register_and_login(client, email_sender)

    create_response = await client.post(
        "/api/v1/saved-searches",
        json={"name": "Skoda alert", "query": {"make": "skoda"}},
        headers=_csrf_headers(client),
    )
    saved_search_id = create_response.json()["id"]
    await _seed_notification(
        session_factory,
        "notified@example.com",
        payload={"saved_search_id": saved_search_id, "saved_search_name": "Skoda alert"},
    )

    list_response = await client.get("/api/v1/me/notifications")
    assert list_response.json()["notifications"][0]["saved_search_deleted"] is False
