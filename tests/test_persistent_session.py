from __future__ import annotations

import pytest

from sage.coordination.session import PersistentSessionManager, SessionManager
from sage.models import Message


@pytest.fixture
async def mgr(tmp_path):
    m = PersistentSessionManager(db_path=str(tmp_path / "sessions.db"))
    await m.initialize()
    return m


@pytest.mark.asyncio
async def test_save_and_load_roundtrip(mgr):
    session = mgr.create("researcher")
    session.add_message(Message(role="user", content="hello"))
    session.add_message(Message(role="assistant", content="world"))
    session.set_metadata("key", "value")

    await mgr.save(session.session_id)

    mgr2 = PersistentSessionManager(db_path=mgr._db_path)
    await mgr2.initialize()

    restored = await mgr2.load(session.session_id)
    assert restored is not None
    assert restored.session_id == session.session_id
    assert restored.agent_name == "researcher"
    assert len(restored.messages) == 2
    assert restored.messages[0].role == "user"
    assert restored.messages[0].content == "hello"
    assert restored.messages[1].role == "assistant"
    assert restored.messages[1].content == "world"
    assert restored.get_metadata("key") == "value"


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(mgr):
    result = await mgr.load("nonexistent-session-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_persisted_returns_metadata_without_messages(mgr):
    s1 = mgr.create("agent-a")
    s1.add_message(Message(role="user", content="ping"))
    s1.add_message(Message(role="assistant", content="pong"))
    await mgr.save(s1.session_id)

    s2 = mgr.create("agent-b")
    await mgr.save(s2.session_id)

    rows = await mgr.list_persisted()
    assert len(rows) == 2

    by_id = {r["id"]: r for r in rows}
    assert by_id[s1.session_id]["message_count"] == 2
    assert by_id[s2.session_id]["message_count"] == 0
    assert "messages" not in by_id[s1.session_id]

    for row in rows:
        assert "id" in row
        assert "agent_name" in row
        assert "created_at" in row
        assert "updated_at" in row
        assert "status" in row


@pytest.mark.asyncio
async def test_list_persisted_filtered_by_agent_name(mgr):
    s1 = mgr.create("target-agent")
    await mgr.save(s1.session_id)
    s2 = mgr.create("other-agent")
    await mgr.save(s2.session_id)

    rows = await mgr.list_persisted(agent_name="target-agent")
    assert len(rows) == 1
    assert rows[0]["agent_name"] == "target-agent"


@pytest.mark.asyncio
async def test_delete_removes_from_sqlite_and_memory(mgr):
    session = mgr.create("researcher")
    await mgr.save(session.session_id)

    found = await mgr.delete(session.session_id)
    assert found is True

    assert mgr.get(session.session_id) is None

    rows = await mgr.list_persisted()
    assert all(r["id"] != session.session_id for r in rows)


@pytest.mark.asyncio
async def test_delete_returns_false_for_missing_session(mgr):
    found = await mgr.delete("ghost-session-id")
    assert found is False


@pytest.mark.asyncio
async def test_fork_creates_independent_copy(mgr):
    original = mgr.create("agent-x")
    original.add_message(Message(role="user", content="original message"))
    original.set_metadata("origin", "true")
    await mgr.save(original.session_id)

    forked = await mgr.fork(original.session_id, new_name="agent-y")

    assert forked.session_id != original.session_id
    assert forked.agent_name == "agent-y"
    assert len(forked.messages) == 1
    assert forked.messages[0].content == "original message"
    assert forked.get_metadata("origin") == "true"

    forked.add_message(Message(role="user", content="forked-only message"))
    original_reloaded = mgr.get(original.session_id)
    assert original_reloaded is not None
    assert len(original_reloaded.messages) == 1


@pytest.mark.asyncio
async def test_fork_loads_from_sqlite_when_not_in_memory(mgr, tmp_path):
    original = mgr.create("researcher")
    original.add_message(Message(role="user", content="persisted"))
    await mgr.save(original.session_id)

    mgr2 = PersistentSessionManager(db_path=str(tmp_path / "sessions.db"))
    await mgr2.initialize()

    forked = await mgr2.fork(original.session_id)
    assert forked.session_id != original.session_id
    assert forked.agent_name == "researcher"
    assert forked.messages[0].content == "persisted"


@pytest.mark.asyncio
async def test_fork_raises_for_unknown_session(mgr):
    with pytest.raises(KeyError):
        await mgr.fork("unknown-session")


@pytest.mark.asyncio
async def test_save_upserts_on_repeated_calls(mgr):
    session = mgr.create("agent-z")
    session.add_message(Message(role="user", content="first"))
    await mgr.save(session.session_id)

    session.add_message(Message(role="assistant", content="second"))
    await mgr.save(session.session_id)

    rows = await mgr.list_persisted()
    assert len(rows) == 1
    assert rows[0]["message_count"] == 2


@pytest.mark.asyncio
async def test_save_raises_for_session_not_in_memory(mgr):
    with pytest.raises(KeyError):
        await mgr.save("not-in-memory")


@pytest.mark.asyncio
async def test_load_populates_memory_cache(mgr):
    session = mgr.create("loader-agent")
    session.add_message(Message(role="user", content="cached"))
    await mgr.save(session.session_id)

    mgr.destroy(session.session_id)
    assert mgr.get(session.session_id) is None

    await mgr.load(session.session_id)
    assert mgr.get(session.session_id) is not None
    assert mgr.count() == 1


def test_session_manager_still_works_standalone():
    sm = SessionManager()
    assert sm.count() == 0

    s = sm.create("agent", metadata={"k": "v"})
    assert sm.count() == 1
    assert sm.get(s.session_id) is s

    sessions = sm.list_sessions(agent_name="agent")
    assert len(sessions) == 1

    removed = sm.destroy(s.session_id)
    assert removed is True
    assert sm.count() == 0
    assert sm.destroy(s.session_id) is False


@pytest.mark.asyncio
async def test_persistent_manager_sync_api_mirrors_session_manager(mgr):
    s = mgr.create("sync-agent", session_id="fixed-id", metadata={"x": 1})
    assert mgr.count() == 1
    assert mgr.get("fixed-id") is s

    results = mgr.list_sessions(agent_name="sync-agent")
    assert len(results) == 1

    removed = mgr.destroy("fixed-id")
    assert removed is True
    assert mgr.count() == 0
