"""Tests for SageExitCode enum."""

from __future__ import annotations


from sage.cli.exit_codes import SageExitCode


class TestSageExitCode:
    def test_success_is_zero(self) -> None:
        assert SageExitCode.SUCCESS == 0

    def test_error_is_one(self) -> None:
        assert SageExitCode.ERROR == 1

    def test_config_error_is_two(self) -> None:
        assert SageExitCode.CONFIG_ERROR == 2

    def test_permission_denied_is_three(self) -> None:
        assert SageExitCode.PERMISSION_DENIED == 3

    def test_max_turns_is_four(self) -> None:
        assert SageExitCode.MAX_TURNS == 4

    def test_timeout_is_five(self) -> None:
        assert SageExitCode.TIMEOUT == 5

    def test_tool_error_is_six(self) -> None:
        assert SageExitCode.TOOL_ERROR == 6

    def test_provider_error_is_seven(self) -> None:
        assert SageExitCode.PROVIDER_ERROR == 7

    def test_is_int(self) -> None:
        """SageExitCode values are real ints (IntEnum)."""
        assert int(SageExitCode.SUCCESS) == 0
        assert int(SageExitCode.CONFIG_ERROR) == 2

    def test_all_values_unique(self) -> None:
        values = [e.value for e in SageExitCode]
        assert len(values) == len(set(values))

    def test_members_count(self) -> None:
        """Exactly 8 codes are defined (0-7)."""
        assert len(SageExitCode) == 8
