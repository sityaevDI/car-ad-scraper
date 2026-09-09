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
        payload={"listing_title": "Skoda Octavia", "listing_price": 10_000, "currency": "EUR"},
    )
    subject, body = render_notification(notification)
    assert "Skoda Octavia" in subject
    assert "10000" in body or "10_000" in body


def test_render_price_drop_shows_before_and_after():
    notification = Notification(
        type=NotificationType.PRICE_DROP,
        payload={"listing_title": "Skoda Octavia", "previous_price": 12_000, "current_price": 10_000, "currency": "EUR"},
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
            user_id=user.id, type=NotificationType.NEW_MATCH, payload={"listing_title": "Skoda"}
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
