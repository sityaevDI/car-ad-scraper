"""Renders and sends the email side of a Notification. Registered as an arq task in
app/scraping/worker.py so a slow/failing SMTP call never blocks or fails the scrape job that
triggered it (see issue #22's isolation requirement).
"""

import uuid
from typing import Any

from app.auth.email import EmailSender
from app.auth.repository import UserRepository
from app.config import get_settings
from app.models.notification import Notification, NotificationType


def _listing_url(listing_id: uuid.UUID | None) -> str:
    if listing_id is None:
        return ""
    return f"{get_settings().frontend_base_url}/listings/{listing_id}"


def render_notification(notification: Notification) -> tuple[str, str]:
    payload = notification.payload or {}
    url = _listing_url(notification.listing_id)

    if notification.type == NotificationType.NEW_MATCH:
        title = payload.get("listing_title", "Новое объявление")
        price = payload.get("listing_price")
        currency = payload.get("currency", "")
        subject = f"Новое совпадение: {title}"
        body = f"{title}\n{price} {currency}\n\nСохранённый поиск: {payload.get('saved_search_name', '')}\n{url}"
        return subject, body

    if notification.type == NotificationType.PRICE_DROP:
        title = payload.get("listing_title", "Объявление")
        previous = payload.get("previous_price")
        current = payload.get("current_price")
        currency = payload.get("currency", "")
        subject = f"Цена снижена: {title}"
        body = f"{title}\nБыло: {previous} {currency}\nСтало: {current} {currency}\n{url}"
        return subject, body

    if notification.type == NotificationType.LISTING_REMOVED:
        title = payload.get("listing_title", "Объявление")
        subject = f"Объявление снято с публикации: {title}"
        body = f"{title}\n{url}"
        return subject, body

    subject = "Изменение на рынке"
    body = payload.get("description", "")
    return subject, body


async def send_notification_email(ctx: dict[str, Any], notification_id: str) -> None:
    session_factory = ctx["session_factory"]
    email_sender: EmailSender = ctx["email_sender"]

    async with session_factory() as session:
        notification = await session.get(Notification, uuid.UUID(notification_id))
        if notification is None:
            return
        user = await UserRepository(session).get_by_id(notification.user_id)
        if user is None:
            return

        subject, body = render_notification(notification)
        await email_sender.send(to=user.email, subject=subject, body=body)
