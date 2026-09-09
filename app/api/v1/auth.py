from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_csrf
from app.auth.email import EmailSender, get_email_sender
from app.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageOut,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.auth.service import AuthService
from app.auth.tokens import generate_token
from app.config import get_settings
from app.db.session import get_session
from app.infrastructure.redis import get_redis
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])


def _get_auth_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    email_sender: EmailSender = Depends(get_email_sender),
) -> AuthService:
    return AuthService(session, redis, email_sender)


def _set_auth_cookies(response: Response, session_id: str) -> None:
    settings = get_settings()
    csrf_token = generate_token()
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        max_age=settings.session_ttl_seconds,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    # Not HttpOnly — the SPA must be able to read it to echo it back as X-CSRF-Token.
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.session_ttl_seconds,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    body: RegisterRequest, response: Response, auth_service: AuthService = Depends(_get_auth_service)
) -> UserOut:
    user, session_id = await auth_service.register(body.email, body.password)
    _set_auth_cookies(response, session_id)
    return UserOut.from_user(user)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(_get_auth_service),
) -> UserOut:
    ip = request.client.host if request.client else "unknown"
    user, session_id = await auth_service.login(body.email, body.password, ip)
    _set_auth_cookies(response, session_id)
    return UserOut.from_user(user)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, auth_service: AuthService = Depends(_get_auth_service)) -> None:
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        require_csrf(request)
        user_id = await auth_service.sessions.get_user_id(session_id)
        if user_id:
            await auth_service.logout(session_id, user_id)
    _clear_auth_cookies(response)


@router.post("/verify-email", response_model=MessageOut)
async def verify_email(body: VerifyEmailRequest, auth_service: AuthService = Depends(_get_auth_service)) -> MessageOut:
    await auth_service.verify_email(body.token)
    return MessageOut(detail="Email verified")


@router.post("/refresh", response_model=UserOut)
async def refresh(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(_get_auth_service),
    _csrf: None = Depends(require_csrf),
) -> UserOut:
    settings = get_settings()
    old_session_id = request.cookies[settings.session_cookie_name]
    new_session_id = await auth_service.refresh(current_user, old_session_id)
    _set_auth_cookies(response, new_session_id)
    return UserOut.from_user(current_user)


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    body: ForgotPasswordRequest, request: Request, auth_service: AuthService = Depends(_get_auth_service)
) -> MessageOut:
    ip = request.client.host if request.client else "unknown"
    await auth_service.forgot_password(body.email, ip)
    return MessageOut(detail="If that email is registered, a reset link has been sent")


@router.post("/reset-password", response_model=MessageOut)
async def reset_password(
    body: ResetPasswordRequest, auth_service: AuthService = Depends(_get_auth_service)
) -> MessageOut:
    await auth_service.reset_password(body.token, body.new_password)
    return MessageOut(detail="Password has been reset")


@me_router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(current_user)
