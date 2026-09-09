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


def _saved_search_url(saved_search_id: str | None) -> str:
    if not saved_search_id:
        return f"{get_settings().frontend_base_url}/saved-searches"
    return f"{get_settings().frontend_base_url}/saved-searches/{saved_search_id}"


def _new_listings_phrase(count: int) -> str:
    """Russian noun/adjective agreement for "N new listings": 1 новое объявление, 2-4 новых
    объявления, 5+ (and the -11..-14 teens exception) новых объявлений.
    """
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} новое объявление"
    if 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        return f"{count} новых объявления"
    return f"{count} новых объявлений"


def render_notification(notification: Notification) -> tuple[str, str]:
    payload = notification.payload or {}
    url = _listing_url(notification.listing_id)

    if notification.type == NotificationType.NEW_MATCH:
        name = payload.get("saved_search_name", "Сохранённый поиск")
        count = payload.get("new_listings_count", 0)
        description = payload.get("query_description", "")
        search_url = _saved_search_url(payload.get("saved_search_id"))
        phrase = _new_listings_phrase(count)
        subject = f"«{name}»: {phrase}"
        body = f"По вашему поиску «{name}» ({description}) появилось: {phrase}.\n\nСмотреть: {search_url}"
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
