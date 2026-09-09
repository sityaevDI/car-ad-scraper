import pytest

from app.auth.cli import _set_role
from app.auth.repository import UserRepository
from app.models.user import UserRole


@pytest.fixture(autouse=True)
def _patch_get_session(monkeypatch, session):
    async def fake_get_session():
        yield session

    monkeypatch.setattr("app.auth.cli.get_session", fake_get_session)


async def test_promote_sets_admin_role(session):
    user = await UserRepository(session).create("person@example.com", "hashed")
    await session.commit()
    assert user.role == UserRole.USER

    await _set_role("person@example.com", UserRole.ADMIN)

    refreshed = await UserRepository(session).get_by_email("person@example.com")
    assert refreshed.role == UserRole.ADMIN


async def test_demote_resets_user_role(session):
    user = await UserRepository(session).create("person@example.com", "hashed")
    await UserRepository(session).set_role(user, UserRole.ADMIN)
    await session.commit()

    await _set_role("person@example.com", UserRole.USER)

    refreshed = await UserRepository(session).get_by_email("person@example.com")
    assert refreshed.role == UserRole.USER


async def test_set_role_raises_for_unknown_email(session):
    with pytest.raises(SystemExit):
        await _set_role("nobody@example.com", UserRole.ADMIN)
