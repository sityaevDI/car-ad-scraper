"""Endpoint-level tests for the scrape job API, following tests/unit/test_auth_endpoints.py's
pattern: real FastAPI app over ASGI, dependency overrides instead of a real Postgres/Redis/arq.
"""

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
from app.models.scrape_job import ScrapeJobStatus
from app.models.user import UserRole
from app.scraping.queue import get_job_enqueuer


class RecordingEmailSender:
    def __init__(self):
        self.sent = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_token(self) -> str:
        return self.sent[-1]["body"].rsplit("token=", 1)[-1]


class RecordingEnqueuer:
    def __init__(self):
        self.enqueued: list[str] = []

    async def __call__(self, job_id: str) -> None:
        self.enqueued.append(job_id)


@pytest.fixture
def email_sender():
    return RecordingEmailSender()


@pytest.fixture
def enqueuer():
    return RecordingEnqueuer()


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
async def client(session_factory, email_sender, enqueuer):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    fake_redis = FakeAsyncRedis(decode_responses=True)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_email_sender] = lambda: email_sender
    app.dependency_overrides[get_job_enqueuer] = lambda: enqueuer

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    settings = get_settings()
    return {settings.csrf_header_name: client.cookies[settings.csrf_cookie_name]}


async def _register_and_login(
    client: AsyncClient,
    email_sender: RecordingEmailSender,
    email: str = "scraper@example.com",
) -> None:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "hunter2pass"})
    token = email_sender.last_token()
    await client.post("/api/v1/auth/verify-email", json={"token": token})
    await client.post("/api/v1/auth/login", json={"email": email, "password": "hunter2pass"})


async def _promote_to_admin(session_factory, email: str = "scraper@example.com") -> None:
    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_email(email)
        await repo.set_role(user, UserRole.ADMIN)
        await session.commit()


async def _register_login_and_promote(
    client: AsyncClient,
    email_sender: RecordingEmailSender,
    session_factory,
    email: str = "scraper@example.com",
) -> None:
    await _register_and_login(client, email_sender, email)
    # get_current_user re-fetches the user row on every request, so the promotion above takes
    # effect immediately without a re-login.
    await _promote_to_admin(session_factory, email)


async def test_create_scrape_job_creates_row_and_enqueues(client, email_sender, session_factory, enqueuer):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/jobs",
        json={"source_code": "polovniautomobili", "query": {"make": "Skoda"}, "max_pages": 1},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == ScrapeJobStatus.PENDING.value
    assert body["query"]["search_query"]["make"] == "Skoda"
    assert body["query"]["max_pages"] == 1
    assert enqueuer.enqueued == [body["id"]]


async def test_create_scrape_job_rejects_unknown_source(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/jobs",
        json={"source_code": "not_a_real_source"},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 400


async def test_create_scrape_job_requires_auth(client):
    response = await client.post("/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"})
    assert response.status_code == 401


async def test_create_scrape_job_requires_admin(client, email_sender):
    await _register_and_login(client, email_sender)

    response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )

    assert response.status_code == 403


async def test_get_scrape_job_returns_created_job(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )
    job_id = create_response.json()["id"]

    response = await client.get(f"/api/v1/scrape/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["id"] == job_id


async def test_get_scrape_job_404_for_unknown_id(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    response = await client.get("/api/v1/scrape/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_cancel_scrape_job_flips_status(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )
    job_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/scrape/jobs/{job_id}/cancel", headers=_csrf_headers(client))

    assert response.status_code == 200
    assert response.json()["status"] == ScrapeJobStatus.CANCELLED.value


async def test_retry_scrape_job_reenqueues_failed_job(client, email_sender, session_factory, enqueuer):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )
    job_id = create_response.json()["id"]
    await client.post(f"/api/v1/scrape/jobs/{job_id}/cancel", headers=_csrf_headers(client))

    response = await client.post(f"/api/v1/scrape/jobs/{job_id}/retry", headers=_csrf_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ScrapeJobStatus.PENDING.value
    assert body["finished_at"] is None
    assert enqueuer.enqueued == [job_id, job_id]


async def test_retry_scrape_job_rejects_non_terminal_job(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )
    job_id = create_response.json()["id"]

    response = await client.post(f"/api/v1/scrape/jobs/{job_id}/retry", headers=_csrf_headers(client))

    assert response.status_code == 400


async def test_list_scrape_jobs_filters_by_status(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client)
    )
    job_id = create_response.json()["id"]
    await client.post(f"/api/v1/scrape/jobs/{job_id}/cancel", headers=_csrf_headers(client))
    await client.post("/api/v1/scrape/jobs", json={"source_code": "polovniautomobili"}, headers=_csrf_headers(client))

    response = await client.get("/api/v1/scrape/jobs", params={"status": ScrapeJobStatus.CANCELLED.value})

    assert response.status_code == 200
    body = response.json()
    assert [job["id"] for job in body] == [job_id]


async def test_list_scrape_jobs_requires_admin(client, email_sender):
    await _register_and_login(client, email_sender)
    response = await client.get("/api/v1/scrape/jobs")
    assert response.status_code == 403


async def test_create_scheduled_scrape(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "query": {"make": "Skoda"}, "max_pages": 2, "interval_minutes": 60},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["job_type"] == "search"
    assert body["interval_minutes"] == 60
    assert body["enabled"] is True
    assert body["query"]["search_query"]["make"] == "Skoda"
    assert body["next_run_at"] is not None
    assert body["last_run_at"] is None


async def test_create_scheduled_scrape_accepts_full_source_refresh_with_empty_query(
    client, email_sender, session_factory
):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "job_type": "full_source_refresh", "interval_minutes": 60},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 201
    assert response.json()["job_type"] == "full_source_refresh"


async def test_create_scheduled_scrape_rejects_filtered_full_source_refresh(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/schedules",
        json={
            "source_code": "polovniautomobili",
            "job_type": "full_source_refresh",
            "query": {"make": "Skoda"},
            "interval_minutes": 60,
        },
        headers=_csrf_headers(client),
    )

    assert response.status_code == 400


async def test_create_scheduled_scrape_rejects_unimplemented_job_type(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "job_type": "listing_refresh", "interval_minutes": 60},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 400


async def test_create_scheduled_scrape_rejects_interval_below_minimum(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)

    response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "interval_minutes": 1},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 422


async def test_list_scheduled_scrapes(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "interval_minutes": 60},
        headers=_csrf_headers(client),
    )

    response = await client.get("/api/v1/scrape/schedules")

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_update_scheduled_scrape_toggles_enabled_and_interval(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "interval_minutes": 60},
        headers=_csrf_headers(client),
    )
    schedule_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/v1/scrape/schedules/{schedule_id}",
        json={"enabled": False, "interval_minutes": 120},
        headers=_csrf_headers(client),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["interval_minutes"] == 120


async def test_delete_scheduled_scrape(client, email_sender, session_factory):
    await _register_login_and_promote(client, email_sender, session_factory)
    create_response = await client.post(
        "/api/v1/scrape/schedules",
        json={"source_code": "polovniautomobili", "interval_minutes": 60},
        headers=_csrf_headers(client),
    )
    schedule_id = create_response.json()["id"]

    response = await client.delete(f"/api/v1/scrape/schedules/{schedule_id}", headers=_csrf_headers(client))
    assert response.status_code == 204

    list_response = await client.get("/api/v1/scrape/schedules")
    assert list_response.json() == []


async def test_scheduled_scrapes_require_admin(client, email_sender):
    await _register_and_login(client, email_sender)
    response = await client.get("/api/v1/scrape/schedules")
    assert response.status_code == 403
