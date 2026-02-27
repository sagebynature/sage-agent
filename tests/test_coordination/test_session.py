"""Tests for SessionState container — Task 7."""

from __future__ import annotations


from sage.coordination.session import SessionState
from sage.models import Message


def _msg(role: str, content: str) -> Message:
    return Message(role=role, content=content)


class TestSessionStateBasics:
    def test_session_id_is_auto_generated(self) -> None:
        s = SessionState(agent_name="test")
        assert s.session_id != ""
        assert len(s.session_id) > 0

    def test_session_ids_are_unique(self) -> None:
        s1 = SessionState(agent_name="a")
        s2 = SessionState(agent_name="b")
        assert s1.session_id != s2.session_id

    def test_agent_name_is_stored(self) -> None:
        s = SessionState(agent_name="my-agent")
        assert s.agent_name == "my-agent"

    def test_created_at_is_set(self) -> None:
        s = SessionState(agent_name="test")
        assert s.created_at > 0

    def test_initial_messages_empty(self) -> None:
        s = SessionState(agent_name="test")
        assert s.get_messages() == []

    def test_initial_tool_results_empty(self) -> None:
        s = SessionState(agent_name="test")
        assert s.tool_results == {}

    def test_initial_metadata_empty(self) -> None:
        s = SessionState(agent_name="test")
        assert s.metadata == {}


class TestSessionStateMessages:
    def test_add_message(self) -> None:
        s = SessionState(agent_name="test")
        msg = _msg("user", "hello")
        s.add_message(msg)
        assert len(s.get_messages()) == 1
        assert s.get_messages()[0].content == "hello"

    def test_add_multiple_messages(self) -> None:
        s = SessionState(agent_name="test")
        s.add_message(_msg("user", "first"))
        s.add_message(_msg("assistant", "second"))
        assert len(s.get_messages()) == 2

    def test_get_messages_with_limit(self) -> None:
        s = SessionState(agent_name="test")
        for i in range(5):
            s.add_message(_msg("user", f"msg {i}"))
        latest = s.get_messages(limit=3)
        assert len(latest) == 3
        # Should return the latest messages
        assert latest[-1].content == "msg 4"

    def test_get_messages_limit_none_returns_all(self) -> None:
        s = SessionState(agent_name="test")
        for i in range(4):
            s.add_message(_msg("user", f"msg {i}"))
        assert len(s.get_messages(limit=None)) == 4


class TestSessionStateMetadata:
    def test_set_and_get_metadata(self) -> None:
        s = SessionState(agent_name="test")
        s.set_metadata("key", "value")
        assert s.get_metadata("key") == "value"

    def test_get_metadata_with_default(self) -> None:
        s = SessionState(agent_name="test")
        assert s.get_metadata("missing", default="fallback") == "fallback"

    def test_get_metadata_default_is_none(self) -> None:
        s = SessionState(agent_name="test")
        assert s.get_metadata("missing") is None

    def test_set_metadata_overwrites(self) -> None:
        s = SessionState(agent_name="test")
        s.set_metadata("k", "old")
        s.set_metadata("k", "new")
        assert s.get_metadata("k") == "new"


class TestSessionStateClear:
    def test_clear_resets_messages(self) -> None:
        s = SessionState(agent_name="test")
        s.add_message(_msg("user", "hello"))
        s.clear()
        assert s.get_messages() == []

    def test_clear_resets_tool_results(self) -> None:
        s = SessionState(agent_name="test")
        s.tool_results["tool1"] = "result"
        s.clear()
        assert s.tool_results == {}

    def test_clear_keeps_metadata(self) -> None:
        s = SessionState(agent_name="test")
        s.set_metadata("key", "value")
        s.clear()
        assert s.get_metadata("key") == "value"


class TestSessionStateIsolation:
    def test_adding_message_to_s1_does_not_affect_s2(self) -> None:
        s1 = SessionState(agent_name="a")
        s2 = SessionState(agent_name="b")
        s1.add_message(_msg("user", "hello"))
        assert len(s1.get_messages()) == 1
        assert len(s2.get_messages()) == 0

    def test_metadata_isolated_between_sessions(self) -> None:
        s1 = SessionState(agent_name="a")
        s2 = SessionState(agent_name="b")
        s1.set_metadata("key", "from_s1")
        assert s2.get_metadata("key") is None

    def test_tool_results_isolated(self) -> None:
        s1 = SessionState(agent_name="a")
        s2 = SessionState(agent_name="b")
        s1.tool_results["t"] = "result"
        assert "t" not in s2.tool_results
