from __future__ import annotations

from sage.complexity import score_turn_complexity
from sage.config import ComplexityConfig
from sage.models import Message, ToolSchema


class TestScoreTurnComplexity:
    def test_message_length_contributes_to_score(self) -> None:
        score = score_turn_complexity(
            messages=[Message(role="user", content="x" * 40)],
            tool_schemas=None,
            config=ComplexityConfig(),
        )
        assert score.score == 10
        assert score.level == "simple"
        assert any(f.kind == "message_length" and f.contribution == 10 for f in score.factors)

    def test_tool_count_contributes_to_score(self) -> None:
        score = score_turn_complexity(
            messages=[Message(role="user", content="hi")],
            tool_schemas=[
                ToolSchema(name="a"),
                ToolSchema(name="b"),
                ToolSchema(name="c"),
            ],
            config=ComplexityConfig(),
        )
        assert score.score == 60
        assert any(f.kind == "tool_count" and f.contribution == 60 for f in score.factors)

    def test_code_markers_contribute_per_match(self) -> None:
        score = score_turn_complexity(
            messages=[
                Message(
                    role="user",
                    content="```python\nasync def run():\n    pass\n```",
                )
            ],
            tool_schemas=None,
            config=ComplexityConfig(code_markers=["async ", "def ", "```"]),
        )
        assert score.score == 99
        assert any(f.kind == "code_markers" and f.contribution == 90 for f in score.factors)

    def test_conversation_depth_over_baseline_contributes(self) -> None:
        messages = [Message(role="user", content=f"m{i}") for i in range(12)]
        score = score_turn_complexity(
            messages=messages,
            tool_schemas=None,
            config=ComplexityConfig(),
        )
        assert score.score == 36
        assert any(f.kind == "conversation_depth" and f.contribution == 30 for f in score.factors)

    def test_long_system_prompt_contributes(self) -> None:
        score = score_turn_complexity(
            messages=[
                Message(role="system", content="s" * 540),
                Message(role="user", content="hello"),
            ],
            tool_schemas=None,
            config=ComplexityConfig(),
        )
        assert score.score == 140
        assert any(f.kind == "system_prompt_length" and f.contribution == 4 for f in score.factors)
        assert score.level == "medium"

    def test_thresholds_map_to_medium_and_complex(self) -> None:
        medium_score = score_turn_complexity(
            messages=[
                Message(role="system", content="s" * 540),
                Message(role="user", content="hello"),
            ],
            tool_schemas=None,
            config=ComplexityConfig(),
        )
        complex_score = score_turn_complexity(
            messages=[Message(role="user", content="x" * 2000)],
            tool_schemas=[ToolSchema(name=f"t{i}") for i in range(20)],
            config=ComplexityConfig(),
        )
        assert medium_score.level == "medium"
        assert complex_score.level == "complex"

    def test_feature_toggles_disable_contributions(self) -> None:
        score = score_turn_complexity(
            messages=[Message(role="user", content="x" * 40)],
            tool_schemas=[ToolSchema(name="a")],
            config=ComplexityConfig(
                features={
                    "message_length": False,
                    "tool_count": False,
                    "code_markers": False,
                    "conversation_depth": False,
                    "system_prompt_length": False,
                }
            ),
        )
        assert score.score == 0
        assert score.factors == []
