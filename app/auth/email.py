import logging
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("app.auth.email")

_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class LoggingEmailSender:
    """Default sender while no real provider is configured — logs the email instead of sending
    it, so register/verify-email/forgot-password/reset-password work end-to-end in local dev and
    CI without any credentials. See app/config.py:resend_api_key.
    """

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.info("Email (not sent, no provider configured) to=%s subject=%r body=%r", to, subject, body)


class ResendEmailSender:
    """Sends via Resend (https://resend.com). A provider hiccup logs a warning rather than
    raising, so a transient email-sending failure doesn't turn into a 500 on register/reset —
    the user can always request a new verification/reset link.
    """

    def __init__(self, api_key: str, from_address: str):
        self._api_key = api_key
        self._from_address = from_address

    async def send(self, to: str, subject: str, body: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    _RESEND_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"from": self._from_address, "to": [to], "subject": subject, "text": body},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                logger.warning("Failed to send email to=%s subject=%r", to, subject, exc_info=True)


def _build_email_sender(settings: Settings) -> EmailSender:
    if settings.resend_api_key:
        return ResendEmailSender(api_key=settings.resend_api_key, from_address=settings.email_from_address)
    return LoggingEmailSender()


@lru_cache
def get_email_sender() -> EmailSender:
    return _build_email_sender(get_settings())
