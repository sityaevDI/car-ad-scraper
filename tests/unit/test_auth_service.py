import pytest
from fastapi import HTTPException

from app.auth.repository import UserRepository
from app.auth.security import verify_password
from app.auth.service import AuthService


class RecordingEmailSender:
    def __init__(self):
        self.sent = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})

    def last_token(self) -> str:
        return self.sent[-1]["body"].rsplit("token=", 1)[-1]


@pytest.fixture
def email_sender():
    return RecordingEmailSender()


@pytest.fixture
def auth_service(session, redis, email_sender):
    return AuthService(session, redis, email_sender)


async def test_register_creates_user_with_hashed_password(auth_service, session):
    user, session_id = await auth_service.register("new@example.com", "correct horse battery")
    assert user.password_hash != "correct horse battery"
    assert verify_password("correct horse battery", user.password_hash)
    assert session_id

    fetched = await UserRepository(session).get_by_email("new@example.com")
    assert fetched is not None


async def test_register_sends_verification_email(auth_service, email_sender):
    await auth_service.register("new@example.com", "correct horse battery")
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to"] == "new@example.com"


async def test_register_creates_a_working_session(auth_service):
    _, session_id = await auth_service.register("new@example.com", "correct horse battery")
    assert await auth_service.sessions.get_user_id(session_id) is not None


async def test_register_duplicate_email_raises_409(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register("new@example.com", "another password")
    assert exc_info.value.status_code == 409


async def test_login_success(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    user, session_id = await auth_service.login("new@example.com", "correct horse battery", ip="127.0.0.1")
    assert user.email == "new@example.com"
    assert await auth_service.sessions.get_user_id(session_id) is not None


async def test_login_wrong_password(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("new@example.com", "wrong password", ip="127.0.0.1")
    assert exc_info.value.status_code == 401


async def test_login_unknown_email(auth_service):
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("nobody@example.com", "whatever", ip="127.0.0.1")
    assert exc_info.value.status_code == 401


async def test_login_rate_limited_after_max_attempts(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    for _ in range(auth_service.settings.login_rate_limit_max_attempts):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login("new@example.com", "wrong password", ip="127.0.0.1")
        assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("new@example.com", "wrong password", ip="127.0.0.1")
    assert exc_info.value.status_code == 429


async def test_login_success_clears_rate_limit_counter(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    with pytest.raises(HTTPException):
        await auth_service.login("new@example.com", "wrong password", ip="127.0.0.1")

    await auth_service.login("new@example.com", "correct horse battery", ip="127.0.0.1")

    key = "login_attempts:127.0.0.1:new@example.com"
    assert await auth_service.rate_limiter.hit(key, limit=1, window_seconds=60) is True


async def test_logout_deletes_session(auth_service):
    user, session_id = await auth_service.register("new@example.com", "correct horse battery")
    await auth_service.logout(session_id, str(user.id))
    assert await auth_service.sessions.get_user_id(session_id) is None


async def test_verify_email_with_valid_token(auth_service, email_sender):
    await auth_service.register("new@example.com", "correct horse battery")
    token = email_sender.last_token()
    await auth_service.verify_email(token)

    fetched = await UserRepository(auth_service.session).get_by_email("new@example.com")
    assert fetched.email_verified_at is not None


async def test_verify_email_token_is_single_use(auth_service, email_sender):
    await auth_service.register("new@example.com", "correct horse battery")
    token = email_sender.last_token()
    await auth_service.verify_email(token)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.verify_email(token)
    assert exc_info.value.status_code == 400


async def test_verify_email_invalid_token(auth_service):
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.verify_email("not-a-real-token")
    assert exc_info.value.status_code == 400


async def test_refresh_rotates_session(auth_service):
    user, old_session_id = await auth_service.register("new@example.com", "correct horse battery")
    new_session_id = await auth_service.refresh(user, old_session_id)
    assert new_session_id != old_session_id
    assert await auth_service.sessions.get_user_id(old_session_id) is None
    assert await auth_service.sessions.get_user_id(new_session_id) == str(user.id)


async def test_forgot_password_sends_email_for_existing_user(auth_service, email_sender):
    await auth_service.register("new@example.com", "correct horse battery")
    email_sender.sent.clear()

    await auth_service.forgot_password("new@example.com", ip="127.0.0.1")
    assert len(email_sender.sent) == 1


async def test_forgot_password_is_generic_for_unknown_email(auth_service, email_sender):
    # Must not raise and must not reveal whether the account exists.
    await auth_service.forgot_password("nobody@example.com", ip="127.0.0.1")
    assert email_sender.sent == []


async def test_forgot_password_rate_limited(auth_service):
    await auth_service.register("new@example.com", "correct horse battery")
    limit = auth_service.settings.password_reset_rate_limit_max_attempts
    for _ in range(limit):
        await auth_service.forgot_password("new@example.com", ip="127.0.0.1")

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.forgot_password("new@example.com", ip="127.0.0.1")
    assert exc_info.value.status_code == 429


async def test_reset_password_with_valid_token(auth_service, email_sender):
    user, old_session_id = await auth_service.register("new@example.com", "correct horse battery")
    await auth_service.forgot_password("new@example.com", ip="127.0.0.1")
    token = email_sender.last_token()

    await auth_service.reset_password(token, "brand new password")

    fetched = await UserRepository(auth_service.session).get_by_id(user.id)
    assert verify_password("brand new password", fetched.password_hash)
    assert not verify_password("correct horse battery", fetched.password_hash)
    # Password reset must kill sessions issued before it.
    assert await auth_service.sessions.get_user_id(old_session_id) is None


async def test_reset_password_invalid_token(auth_service):
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.reset_password("not-a-real-token", "brand new password")
    assert exc_info.value.status_code == 400
