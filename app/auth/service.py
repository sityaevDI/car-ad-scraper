import uuid

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email import EmailSender
from app.auth.rate_limit import RateLimiter
from app.auth.repository import UserRepository
from app.auth.security import hash_password, verify_password
from app.auth.sessions import SessionStore
from app.auth.tokens import OneTimeTokenStore
from app.config import get_settings
from app.models.user import User


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis, email_sender: EmailSender):
        self.session = session
        self.email_sender = email_sender
        self.settings = get_settings()
        self.users = UserRepository(session)
        self.rate_limiter = RateLimiter(redis)
        self.sessions = SessionStore(redis, ttl_seconds=self.settings.session_ttl_seconds)
        self.email_verify_tokens = OneTimeTokenStore(
            redis, "email_verify", self.settings.email_verification_ttl_seconds
        )
        self.password_reset_tokens = OneTimeTokenStore(
            redis, "password_reset", self.settings.password_reset_ttl_seconds
        )

    async def register(self, email: str, password: str) -> tuple[User, str]:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Email is already registered")

        try:
            user = await self.users.create(email, hash_password(password))
        except IntegrityError:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Email is already registered") from None
        await self.session.commit()

        token = await self.email_verify_tokens.issue(str(user.id))
        verify_link = f"{self.settings.frontend_base_url}/verify-email?token={token}"
        await self.email_sender.send(
            to=user.email, subject="Verify your email", body=f"Confirm your email: {verify_link}"
        )

        session_id = await self.sessions.create(str(user.id))
        return user, session_id

    async def login(self, email: str, password: str, ip: str) -> tuple[User, str]:
        rate_key = f"login_attempts:{ip}:{email.lower()}"
        allowed = await self.rate_limiter.hit(
            rate_key, self.settings.login_rate_limit_max_attempts, self.settings.login_rate_limit_window_seconds
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many login attempts, try again later")

        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        await self.rate_limiter.reset(rate_key)
        await self.users.update_last_login(user)
        await self.session.commit()

        session_id = await self.sessions.create(str(user.id))
        return user, session_id

    async def logout(self, session_id: str, user_id: str) -> None:
        await self.sessions.delete(session_id, user_id)

    async def verify_email(self, token: str) -> None:
        user = await self._resolve_one_time_token(self.email_verify_tokens, token)
        await self.users.mark_email_verified(user)
        await self.session.commit()

    async def refresh(self, user: User, old_session_id: str) -> str:
        return await self.sessions.rotate(old_session_id, str(user.id))

    async def forgot_password(self, email: str, ip: str) -> None:
        rate_key = f"pwreset_attempts:{ip}:{email.lower()}"
        allowed = await self.rate_limiter.hit(
            rate_key,
            self.settings.password_reset_rate_limit_max_attempts,
            self.settings.password_reset_rate_limit_window_seconds,
        )
        if not allowed:
            raise HTTPException(status_code=429, detail="Too many password reset requests, try again later")

        # Always the same response whether or not the email exists — avoids account enumeration.
        user = await self.users.get_by_email(email)
        if user is not None:
            token = await self.password_reset_tokens.issue(str(user.id))
            reset_link = f"{self.settings.frontend_base_url}/reset-password?token={token}"
            await self.email_sender.send(
                to=user.email, subject="Reset your password", body=f"Reset your password: {reset_link}"
            )

    async def reset_password(self, token: str, new_password: str) -> None:
        user = await self._resolve_one_time_token(self.password_reset_tokens, token)
        await self.users.update_password_hash(user, hash_password(new_password))
        await self.session.commit()
        # A compromised password should not leave existing sessions alive.
        await self.sessions.revoke_all_for_user(str(user.id))

    async def _resolve_one_time_token(self, store: OneTimeTokenStore, token: str) -> User:
        user_id = await store.consume(token)
        user = await self.users.get_by_id(uuid.UUID(user_id)) if user_id else None
        if user is None:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        return user
