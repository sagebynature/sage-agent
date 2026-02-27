"""Tests for sage.coordination.session — SessionState and SessionManager."""

from __future__ import annotations


from sage.coordination.session import SessionManager, SessionState
from sage.models import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg(role: str, content: str) -> Message:
    return Message(role=role, content=content)


# ---------------------------------------------------------------------------
# SessionState tests
# ---------------------------------------------------------------------------


class TestSessionState:
    def test_add_and_get_messages(self) -> None:
        session = SessionState(session_id="s1", agent_name="agent-a")
        session.add_message(_msg("user", "hello"))
        session.add_message(_msg("assistant", "hi"))
        msgs = session.get_messages()
        assert len(msgs) == 2
        assert msgs[0].content == "hello"
        assert msgs[1].content == "hi"

    def test_get_messages_returns_copy(self) -> None:
        session = SessionState(session_id="s1", agent_name="agent-a")
        session.add_message(_msg("user", "hello"))
        msgs = session.get_messages()
        msgs.append(_msg("user", "extra"))
        assert len(session.get_messages()) == 1

    def test_set_and_get_metadata(self) -> None:
        session = SessionState(session_id="s1", agent_name="agent-a")
        session.set_metadata("key", "value")
        assert session.get_metadata("key") == "value"

    def test_get_metadata_default(self) -> None:
        session = SessionState(session_id="s1", agent_name="agent-a")
        assert session.get_metadata("missing") is None
        assert session.get_metadata("missing", "default") == "default"

    def test_clear(self) -> None:
        session = SessionState(session_id="s1", agent_name="agent-a")
        session.add_message(_msg("user", "hello"))
        session.set_metadata("key", "val")
        session.tool_results["t1"] = "result"
        session.clear()
        assert session.get_messages() == []
        # metadata is intentionally preserved on clear
        assert session.metadata == {"key": "val"}
        assert session.tool_results == {}


# ---------------------------------------------------------------------------
# SessionManager tests
# ---------------------------------------------------------------------------


class TestSessionManager:
    def test_create_session(self) -> None:
        sm = SessionManager()
        session = sm.create("agent-a")
        assert isinstance(session, SessionState)
        assert session.agent_name == "agent-a"

    def test_create_session_auto_id(self) -> None:
        sm = SessionManager()
        session = sm.create("agent-a")
        assert session.session_id is not None
        assert session.session_id != ""

    def test_create_session_custom_id(self) -> None:
        sm = SessionManager()
        session = sm.create("agent-a", session_id="my-custom-id")
        assert session.session_id == "my-custom-id"

    def test_get_session(self) -> None:
        sm = SessionManager()
        created = sm.create("agent-a", session_id="abc123")
        retrieved = sm.get("abc123")
        assert retrieved is created

    def test_get_session_not_found(self) -> None:
        sm = SessionManager()
        assert sm.get("nonexistent") is None

    def test_list_sessions_all(self) -> None:
        sm = SessionManager()
        sm.create("agent-a", session_id="s1")
        sm.create("agent-b", session_id="s2")
        sm.create("agent-a", session_id="s3")
        sessions = sm.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_filter_by_agent(self) -> None:
        sm = SessionManager()
        sm.create("agent-a", session_id="s1")
        sm.create("agent-b", session_id="s2")
        sm.create("agent-a", session_id="s3")
        sessions = sm.list_sessions(agent_name="agent-a")
        assert len(sessions) == 2
        assert all(s.agent_name == "agent-a" for s in sessions)

    def test_destroy_session(self) -> None:
        sm = SessionManager()
        sm.create("agent-a", session_id="s1")
        result = sm.destroy("s1")
        assert result is True
        assert sm.get("s1") is None

    def test_destroy_session_not_found(self) -> None:
        sm = SessionManager()
        result = sm.destroy("nonexistent")
        assert result is False

    def test_count(self) -> None:
        sm = SessionManager()
        assert sm.count() == 0
        sm.create("agent-a", session_id="s1")
        assert sm.count() == 1
        sm.create("agent-b", session_id="s2")
        assert sm.count() == 2
        sm.destroy("s1")
        assert sm.count() == 1

    def test_sessions_isolated(self) -> None:
        sm = SessionManager()
        s1 = sm.create("agent-a", session_id="s1")
        s2 = sm.create("agent-a", session_id="s2")

        s1.add_message(_msg("user", "hello from s1"))
        s2.add_message(_msg("user", "hello from s2"))
        s2.add_message(_msg("assistant", "reply from s2"))

        assert len(s1.get_messages()) == 1
        assert len(s2.get_messages()) == 2
        assert s1.get_messages()[0].content == "hello from s1"
        assert s2.get_messages()[0].content == "hello from s2"
