from app.auth.sessions import SessionStore


async def test_create_and_get_user_id(redis):
    store = SessionStore(redis, ttl_seconds=60)
    session_id = await store.create("user-1")
    assert await store.get_user_id(session_id) == "user-1"


async def test_get_user_id_unknown_session_returns_none(redis):
    store = SessionStore(redis, ttl_seconds=60)
    assert await store.get_user_id("never-created") is None


async def test_delete_removes_session(redis):
    store = SessionStore(redis, ttl_seconds=60)
    session_id = await store.create("user-1")
    await store.delete(session_id, "user-1")
    assert await store.get_user_id(session_id) is None


async def test_rotate_issues_new_id_and_invalidates_old(redis):
    store = SessionStore(redis, ttl_seconds=60)
    old_id = await store.create("user-1")
    new_id = await store.rotate(old_id, "user-1")
    assert new_id != old_id
    assert await store.get_user_id(old_id) is None
    assert await store.get_user_id(new_id) == "user-1"


async def test_revoke_all_for_user_removes_every_session(redis):
    store = SessionStore(redis, ttl_seconds=60)
    id_a = await store.create("user-1")
    id_b = await store.create("user-1")
    await store.revoke_all_for_user("user-1")
    assert await store.get_user_id(id_a) is None
    assert await store.get_user_id(id_b) is None


async def test_revoke_all_for_user_does_not_affect_other_users(redis):
    store = SessionStore(redis, ttl_seconds=60)
    victim_session = await store.create("user-1")
    other_session = await store.create("user-2")
    await store.revoke_all_for_user("user-1")
    assert await store.get_user_id(victim_session) is None
    assert await store.get_user_id(other_session) == "user-2"


async def test_user_sessions_set_ttl_is_armed(redis):
    store = SessionStore(redis, ttl_seconds=60)
    await store.create("user-1")
    ttl = await redis.ttl("user_sessions:user-1")
    assert 0 < ttl <= 60
