import uuid
from datetime import timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.notification import NotificationType
from app.notifications.service import NotificationService


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_notify_creates_notification_and_enqueues_email(session):
    enqueued = []

    async def enqueue_email(notification_id: str) -> None:
        enqueued.append(notification_id)

    service = NotificationService(session, enqueue_email=enqueue_email)
    user_id = uuid.uuid4()

    notification = await service.notify(user_id, NotificationType.NEW_MATCH, {"listing_title": "Skoda"})

    assert notification is not None
    assert notification.user_id == user_id
    assert enqueued == [str(notification.id)]


async def test_notify_without_enqueue_email_still_creates_notification(session):
    service = NotificationService(session)
    notification = await service.notify(uuid.uuid4(), NotificationType.LISTING_REMOVED, {})
    assert notification is not None


async def test_notify_skips_duplicate_within_cooldown(session):
    service = NotificationService(session)
    user_id = uuid.uuid4()
    listing_id = uuid.uuid4()

    first = await service.notify(
        user_id, NotificationType.PRICE_DROP, {"previous_price": 100}, listing_id=listing_id
    )
    second = await service.notify(
        user_id, NotificationType.PRICE_DROP, {"previous_price": 90}, listing_id=listing_id
    )

    assert first is not None
    assert second is None


async def test_notify_allows_duplicate_outside_cooldown(session):
    service = NotificationService(session)
    user_id = uuid.uuid4()
    listing_id = uuid.uuid4()

    first = await service.notify(
        user_id, NotificationType.PRICE_DROP, {}, listing_id=listing_id, cooldown=timedelta(seconds=0)
    )
    second = await service.notify(
        user_id, NotificationType.PRICE_DROP, {}, listing_id=listing_id, cooldown=timedelta(seconds=0)
    )

    assert first is not None
    assert second is not None


async def test_notify_does_not_dedup_across_different_types(session):
    service = NotificationService(session)
    user_id = uuid.uuid4()
    listing_id = uuid.uuid4()

    new_match = await service.notify(user_id, NotificationType.NEW_MATCH, {}, listing_id=listing_id)
    price_drop = await service.notify(user_id, NotificationType.PRICE_DROP, {}, listing_id=listing_id)

    assert new_match is not None
    assert price_drop is not None
