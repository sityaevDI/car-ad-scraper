import secrets
import uuid

from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import UserRepository
from app.auth.sessions import SessionStore
from app.config import get_settings
from app.db.session import get_session
from app.infrastructure.redis import get_redis
from app.models.user import User, UserRole


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> User:
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    store = SessionStore(redis, ttl_seconds=settings.session_ttl_seconds)
    user_id = await store.get_user_id(session_id)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    try:
        user = await UserRepository(session).get_by_id(uuid.UUID(user_id))
    except ValueError:
        user = None
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_csrf(request: Request) -> None:
    settings = get_settings()
    cookie_value = request.cookies.get(settings.csrf_cookie_name)
    header_value = request.headers.get(settings.csrf_header_name)
    if not cookie_value or not header_value or not secrets.compare_digest(cookie_value, header_value):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
