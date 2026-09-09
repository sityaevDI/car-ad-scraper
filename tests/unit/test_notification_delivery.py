import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.notifications.delivery import render_notification, send_notification_email


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


class RecordingEmailSender:
    def __init__(self):
        self.sent = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


def test_render_new_match():
    notification = Notification(
        type=NotificationType.NEW_MATCH,
        payload={
            "saved_search_id": "11111111-1111-1111-1111-111111111111",
            "saved_search_name": "Skoda всех годов",
            "new_listings_count": 3,
            "query_description": "Skoda",
        },
    )
    subject, body = render_notification(notification)
    assert "Skoda всех годов" in subject
    assert "3" in subject
    assert "Skoda всех годов" in body
    assert "Skoda" in body  # query_description
    assert "/saved-searches/11111111-1111-1111-1111-111111111111" in body


def test_render_new_match_agrees_singular_plural_forms():
    def subject_for(count: int) -> str:
        notification = Notification(
            type=NotificationType.NEW_MATCH,
            payload={"saved_search_name": "X", "new_listings_count": count, "query_description": ""},
        )
        return render_notification(notification)[0]

    assert "1 новое объявление" in subject_for(1)
    assert "2 новых объявления" in subject_for(2)
    assert "5 новых объявлений" in subject_for(5)
    assert "11 новых объявлений" in subject_for(11)
    assert "21 новое объявление" in subject_for(21)


def test_render_new_match_includes_updated_count_in_body():
    notification = Notification(
        type=NotificationType.NEW_MATCH,
        payload={
            "saved_search_name": "Skoda всех годов",
            "new_listings_count": 2,
            "updated_listings_count": 5,
            "query_description": "Skoda",
        },
    )
    subject, body = render_notification(notification)
    assert "2 новых объявления" in subject
    assert "Новых объявлений: 2" in body
    assert "Обновлено объявлений: 5" in body


def test_render_new_match_with_only_updates_no_new_listings():
    notification = Notification(
        type=NotificationType.NEW_MATCH,
        payload={
            "saved_search_name": "Skoda всех годов",
            "new_listings_count": 0,
            "updated_listings_count": 4,
            "query_description": "Skoda",
        },
    )
    subject, body = render_notification(notification)
    assert "обновлено 4 объявления" in subject
    assert "Новых объявлений: 0" in body
    assert "Обновлено объявлений: 4" in body


def test_render_new_match_omits_updated_line_when_nothing_updated():
    notification = Notification(
        type=NotificationType.NEW_MATCH,
        payload={"saved_search_name": "X", "new_listings_count": 1, "query_description": ""},
    )
    _, body = render_notification(notification)
    assert "Обновлено" not in body


def test_render_price_drop_shows_before_and_after():
    notification = Notification(
        type=NotificationType.PRICE_DROP,
        payload={
            "listing_title": "Skoda Octavia",
            "previous_price": 12_000,
            "current_price": 10_000,
            "currency": "EUR",
        },
    )
    subject, body = render_notification(notification)
    assert "Skoda Octavia" in subject
    assert "12000" in body
    assert "10000" in body


async def test_send_notification_email_delivers_to_owning_user(session_factory):
    async with session_factory() as session:
        user = User(email="target@example.com", password_hash="x")
        session.add(user)
        await session.flush()
        notification = Notification(
            user_id=user.id,
            type=NotificationType.NEW_MATCH,
            payload={"saved_search_name": "Skoda", "new_listings_count": 1, "query_description": "Skoda"},
        )
        session.add(notification)
        await session.commit()
        notification_id = str(notification.id)

    email_sender = RecordingEmailSender()
    ctx = {"session_factory": session_factory, "email_sender": email_sender}

    await send_notification_email(ctx, notification_id)

    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "target@example.com"
    assert "Skoda" in email_sender.sent[0]["subject"]


async def test_send_notification_email_skips_unknown_notification(session_factory):
    email_sender = RecordingEmailSender()
    ctx = {"session_factory": session_factory, "email_sender": email_sender}

    await send_notification_email(ctx, str(uuid.uuid4()))

    assert email_sender.sent == []
