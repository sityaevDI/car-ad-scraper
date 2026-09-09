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


def _listings_noun(count: int) -> str:
    """Russian noun plural forms: 1 объявление, 2-4 объявления, 5+ (and the -11..-14 teens
    exception) объявлений.
    """
    if count % 10 == 1 and count % 100 != 11:
        return "объявление"
    if 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        return "объявления"
    return "объявлений"


def _new_listings_phrase(count: int) -> str:
    """Russian adjective agreement on top of _listings_noun: "N новое объявление"/"N новых
    объявления"/"N новых объявлений".
    """
    adjective = "новое" if count % 10 == 1 and count % 100 != 11 else "новых"
    return f"{count} {adjective} {_listings_noun(count)}"


def render_notification(notification: Notification) -> tuple[str, str]:
    payload = notification.payload or {}
    url = _listing_url(notification.listing_id)

    if notification.type == NotificationType.NEW_MATCH:
        name = payload.get("saved_search_name", "Сохранённый поиск")
        new_count = payload.get("new_listings_count", 0)
        updated_count = payload.get("updated_listings_count", 0)
        description = payload.get("query_description", "")
        search_url = _saved_search_url(payload.get("saved_search_id"))

        if new_count:
            subject = f"«{name}»: {_new_listings_phrase(new_count)}"
        else:
            subject = f"«{name}»: обновлено {updated_count} {_listings_noun(updated_count)}"

        lines = [f"По вашему поиску «{name}» ({description}):", f"Новых объявлений: {new_count}"]
        if updated_count:
            lines.append(f"Обновлено объявлений: {updated_count}")
        lines += ["", f"Смотреть: {search_url}"]
        body = "\n".join(lines)
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
