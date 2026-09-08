"""Endpoint-level tests driving the real FastAPI app over ASGI, not just the service layer —
covers router wiring, actual Set-Cookie behavior, and CSRF enforcement that a pure service-layer
test can't see.
"""

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
async def client(email_sender):
    # StaticPool + a shared connect_args keeps every get_session() call in this test on the same
    # in-memory sqlite DB — without it, each dependency call would get its own throwaway DB and
    # state wouldn't persist across the multiple HTTP calls in a flow (unlike tests/conftest.py's
    # `session` fixture, which only ever opens one session per test).
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

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
    await engine.dispose()


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    settings = get_settings()
    return {settings.csrf_header_name: client.cookies[settings.csrf_cookie_name]}


async def test_register_sets_cookies_with_expected_attributes(client):
    response = await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    assert response.status_code == 201

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert len(set_cookie_headers) == 2

    sid_header = next(h for h in set_cookie_headers if h.startswith("sid="))
    csrf_header = next(h for h in set_cookie_headers if h.startswith("csrf_token="))

    assert "HttpOnly" in sid_header
    assert "HttpOnly" not in csrf_header
    for header in (sid_header, csrf_header):
        assert "Path=/" in header
        assert "SameSite=lax" in header


async def test_full_flow_register_verify_login_me_refresh_logout(client, email_sender):
    register_response = await client.post(
        "/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"}
    )
    assert register_response.status_code == 201
    assert register_response.json()["email_verified"] is False

    token = email_sender.last_token()
    verify_response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 200

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "hunter2pass"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["email_verified"] is True

    me_response = await client.get("/api/v1/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "new@example.com"

    old_sid = client.cookies[get_settings().session_cookie_name]
    refresh_response = await client.post("/api/v1/auth/refresh", headers=_csrf_headers(client))
    assert refresh_response.status_code == 200
    new_sid = client.cookies[get_settings().session_cookie_name]
    assert new_sid != old_sid

    logout_response = await client.post("/api/v1/auth/logout", headers=_csrf_headers(client))
    assert logout_response.status_code == 204

    me_after_logout = await client.get("/api/v1/me")
    assert me_after_logout.status_code == 401


async def test_refresh_without_csrf_header_is_rejected(client):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 403


async def test_refresh_with_wrong_csrf_header_is_rejected(client):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    settings = get_settings()
    response = await client.post("/api/v1/auth/refresh", headers={settings.csrf_header_name: "wrong-token"})
    assert response.status_code == 403


async def test_logout_without_session_cookie_is_a_no_op(client):
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204


async def test_me_without_session_returns_401(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_duplicate_register_returns_409(client):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    response = await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "other-pass"})
    assert response.status_code == 409


async def test_disposable_email_domain_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "new@mailinator.com", "password": "hunter2pass"}
    )
    assert response.status_code == 422


async def test_login_is_rate_limited_after_too_many_attempts(client):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    limit = get_settings().login_rate_limit_max_attempts

    for _ in range(limit):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "new@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 429


async def test_forgot_password_and_reset_flow(client, email_sender):
    await client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})
    email_sender.sent.clear()

    forgot_response = await client.post("/api/v1/auth/forgot-password", json={"email": "new@example.com"})
    assert forgot_response.status_code == 200

    token = email_sender.last_token()
    reset_response = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"}
    )
    assert reset_response.status_code == 200

    old_password_login = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "hunter2pass"}
    )
    assert old_password_login.status_code == 401

    new_password_login = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "brand-new-pass"}
    )
    assert new_password_login.status_code == 200


async def test_forgot_password_for_unknown_email_still_returns_200(client, email_sender):
    response = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert email_sender.sent == []
