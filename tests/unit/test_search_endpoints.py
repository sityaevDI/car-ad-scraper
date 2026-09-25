"""Endpoint-level tests for the search API, following tests/unit/test_saved_search_endpoints.py's
pattern: real FastAPI app over ASGI, dependency overrides instead of a real Postgres/Redis/arq.
"""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.email import get_email_sender
from app.db.base import Base
from app.db.session import get_session
from app.infrastructure.redis import get_redis
from app.main import app

pytestmark = pytest.mark.asyncio


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


async def _register_and_login(
    client: AsyncClient, email_sender: RecordingEmailSender, email: str = "searcher@example.com"
) -> None:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter2pass"})
    token = email_sender.last_token()
    await client.post("/api/v1/auth/verify-email", json={"token": token})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})


async def test_search_requires_auth(client):
    response = await client.post("/api/v1/search", json={})
    assert response.status_code == 401


async def test_grouped_search_requires_auth(client):
    response = await client.post("/api/v1/search", json={"group_by": ["make", "model"]})
    assert response.status_code == 401


async def test_search_succeeds_when_logged_in(client, email_sender):
    await _register_and_login(client, email_sender)

    response = await client.post("/api/v1/search", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["total_listings"] == 0
