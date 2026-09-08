import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.repository import UserRepository


async def test_create_and_get_by_email(session):
    repo = UserRepository(session)
    user = await repo.create("Person@Example.com", "hashed")
    assert user.email == "person@example.com"

    fetched = await repo.get_by_email("Person@Example.com")
    assert fetched is not None
    assert fetched.id == user.id


async def test_get_by_id(session):
    repo = UserRepository(session)
    user = await repo.create("person@example.com", "hashed")
    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == "person@example.com"


async def test_get_by_email_unknown_returns_none(session):
    repo = UserRepository(session)
    assert await repo.get_by_email("nobody@example.com") is None


async def test_duplicate_email_raises_integrity_error(session):
    repo = UserRepository(session)
    await repo.create("person@example.com", "hashed")
    with pytest.raises(IntegrityError):
        await repo.create("person@example.com", "other-hash")


async def test_mark_email_verified(session):
    repo = UserRepository(session)
    user = await repo.create("person@example.com", "hashed")
    assert user.email_verified_at is None
    await repo.mark_email_verified(user)
    assert user.email_verified_at is not None


async def test_update_password_hash(session):
    repo = UserRepository(session)
    user = await repo.create("person@example.com", "old-hash")
    await repo.update_password_hash(user, "new-hash")
    assert user.password_hash == "new-hash"


async def test_update_last_login(session):
    repo = UserRepository(session)
    user = await repo.create("person@example.com", "hashed")
    assert user.last_login_at is None
    await repo.update_last_login(user)
    assert user.last_login_at is not None
