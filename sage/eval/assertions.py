"""Assertion types and runner for eval test cases."""

from __future__ import annotations
import json
import logging
import re
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


class AssertionResult(BaseModel):
    """The result of running a single assertion."""

    type: str
    passed: bool
    score: float  # 0.0-1.0
    message: str = ""


# ---------------------------------------------------------------------------
# Assertion types
# ---------------------------------------------------------------------------


class BaseAssertion(BaseModel):
    """Base class for all assertion types."""

    pass


class ExactMatchAssertion(BaseAssertion):
    type: Literal["exact_match"]
    value: str


class ContainsAssertion(BaseAssertion):
    type: Literal["contains"]
    value: str


class NotContainsAssertion(BaseAssertion):
    type: Literal["not_contains"]
    value: str


class RegexAssertion(BaseAssertion):
    type: Literal["regex"]
    pattern: str


class JsonSchemaAssertion(BaseAssertion):
    type: Literal["json_schema"]
    schema_: dict[str, Any] = Field(alias="schema")

    model_config = {"populate_by_name": True}


class PythonAssertion(BaseAssertion):
    type: Literal["python"]
    code: str  # Python code returning float 0-1; variable `output` is set


class LLMJudgeAssertion(BaseAssertion):
    type: Literal["llm_judge"]
    min_score: float = 3.0  # 1-5 scale
    rubric: str = "default"


class ToolCallsAssertion(BaseAssertion):
    type: Literal["tool_calls"]
    expected: list[str]  # tool names that MUST have been called


class NoToolCallsAssertion(BaseAssertion):
    type: Literal["no_tool_calls"]
    forbidden: list[str]  # tool names that must NOT have been called


class CostUnderAssertion(BaseAssertion):
    type: Literal["cost_under"]
    max_cost: float  # in USD


class TurnsUnderAssertion(BaseAssertion):
    type: Literal["turns_under"]
    max_turns: int


AssertionConfig = Annotated[
    Union[
        ExactMatchAssertion,
        ContainsAssertion,
        NotContainsAssertion,
        RegexAssertion,
        JsonSchemaAssertion,
        PythonAssertion,
        LLMJudgeAssertion,
        ToolCallsAssertion,
        NoToolCallsAssertion,
        CostUnderAssertion,
        TurnsUnderAssertion,
    ],
    Field(discriminator="type"),
]

# ---------------------------------------------------------------------------
# Rubric descriptions for LLM judge
# ---------------------------------------------------------------------------

_RUBRIC_DESCRIPTIONS: dict[str, str] = {
    "default": (
        "Evaluate on: relevance (2.0), accuracy (2.0), completeness (1.5), "
        "clarity (1.0), efficiency (1.0)."
    ),
    "code_generation": (
        "Evaluate on: correctness (2.5), completeness (2.0), code_quality (1.5), "
        "security (1.5), documentation (1.0)."
    ),
    "qa": (
        "Evaluate on: accuracy (2.5), relevance (2.0), depth (1.5), "
        "source_usage (1.0), conciseness (1.0)."
    ),
}


async def _llm_judge_score(
    output: str,
    rubric_name: str = "default",
    model: str = "gpt-4o",
) -> tuple[float, str]:
    """Call an LLM to score output on a 1-5 scale.

    Returns (raw_score, reasoning).
    """
    import litellm  # lazy import

    rubric_description = _RUBRIC_DESCRIPTIONS.get(rubric_name, _RUBRIC_DESCRIPTIONS["default"])
    system_prompt = (
        "You are an expert evaluator. Score the following output from 1 to 5.\n"
        f"Rubric: {rubric_description}\n"
        'Respond with JSON only: {"score": <1-5>, "reasoning": "<brief>"}'
    )
    user_prompt = f"Output to evaluate:\n\n{output}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.0}

    # Use json_object response format when supported
    try:
        if litellm.supports_response_schema(model, None):
            kwargs["response_format"] = {"type": "json_object"}
    except Exception:
        pass

    response = await litellm.acompletion(**kwargs)
    raw_content = response.choices[0].message.content or ""

    # Strip markdown code fences
    raw_content = re.sub(
        r"^```(?:json)?\n?|```$", "", raw_content.strip(), flags=re.MULTILINE
    ).strip()

    try:
        parsed = json.loads(raw_content)
        score = float(parsed.get("score", 1))
        reasoning = str(parsed.get("reasoning", ""))
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM judge returned unparseable JSON: %r", raw_content)
        score = 1.0
        reasoning = "Could not parse score"

    return score, reasoning


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_assertion(
    assertion: AssertionConfig,
    output: str,
    tool_calls_made: list[str],
    cost: float,
    turns: int,
    judge_model: str = "gpt-4o",
    rubric_name: str = "default",
) -> AssertionResult:
    """Execute a single assertion and return the result."""

    assertion_type = assertion.type

    # -- exact_match --
    if isinstance(assertion, ExactMatchAssertion):
        passed = output == assertion.value
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Expected exact: {assertion.value!r}",
        )

    # -- contains --
    if isinstance(assertion, ContainsAssertion):
        passed = assertion.value in output
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Expected substring: {assertion.value!r}",
        )

    # -- not_contains --
    if isinstance(assertion, NotContainsAssertion):
        passed = assertion.value not in output
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Forbidden substring found: {assertion.value!r}",
        )

    # -- regex --
    if isinstance(assertion, RegexAssertion):
        match = re.search(assertion.pattern, output)
        passed = match is not None
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Regex did not match: {assertion.pattern!r}",
        )

    # -- json_schema --
    if isinstance(assertion, JsonSchemaAssertion):
        try:
            import jsonschema  # type: ignore[import-untyped]  # optional dep

            try:
                data = json.loads(output)
            except json.JSONDecodeError as exc:
                return AssertionResult(
                    type=assertion_type,
                    passed=False,
                    score=0.0,
                    message=f"Output is not valid JSON: {exc}",
                )

            try:
                jsonschema.validate(instance=data, schema=assertion.schema_)
                return AssertionResult(type=assertion_type, passed=True, score=1.0)
            except jsonschema.ValidationError as exc:
                return AssertionResult(
                    type=assertion_type,
                    passed=False,
                    score=0.0,
                    message=str(exc.message),
                )
        except ImportError:
            logger.warning(
                "jsonschema not installed; json_schema assertion skipped. "
                "Install with: pip install sage-agent[eval]"
            )
            return AssertionResult(
                type=assertion_type,
                passed=False,
                score=0.0,
                message="jsonschema package not installed",
            )

    # -- python --
    if isinstance(assertion, PythonAssertion):
        namespace: dict[str, Any] = {"output": output, "result": 0.0}
        try:
            exec(assertion.code, namespace)  # noqa: S102
            raw_result = float(namespace.get("result", 0.0))
        except Exception as exc:
            return AssertionResult(
                type=assertion_type,
                passed=False,
                score=0.0,
                message=f"Python assertion raised: {exc}",
            )
        score_val = max(0.0, min(1.0, raw_result))
        passed = score_val >= 0.5
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=score_val,
            message="" if passed else f"Python assertion score {score_val:.2f} < 0.5",
        )

    # -- llm_judge --
    if isinstance(assertion, LLMJudgeAssertion):
        rubric = assertion.rubric if assertion.rubric != "default" else rubric_name
        try:
            raw_score, reasoning = await _llm_judge_score(output, rubric, judge_model)
        except Exception as exc:
            return AssertionResult(
                type=assertion_type,
                passed=False,
                score=0.0,
                message=f"LLM judge error: {exc}",
            )
        passed = raw_score >= assertion.min_score
        score_val = raw_score / 5.0
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=score_val,
            message=reasoning,
        )

    # -- tool_calls --
    if isinstance(assertion, ToolCallsAssertion):
        missing = [t for t in assertion.expected if t not in tool_calls_made]
        passed = len(missing) == 0
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Missing tool calls: {missing}",
        )

    # -- no_tool_calls --
    if isinstance(assertion, NoToolCallsAssertion):
        found = [t for t in assertion.forbidden if t in tool_calls_made]
        passed = len(found) == 0
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Forbidden tool calls found: {found}",
        )

    # -- cost_under --
    if isinstance(assertion, CostUnderAssertion):
        passed = cost < assertion.max_cost
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Cost {cost:.4f} >= max {assertion.max_cost:.4f}",
        )

    # -- turns_under --
    if isinstance(assertion, TurnsUnderAssertion):
        passed = turns < assertion.max_turns
        return AssertionResult(
            type=assertion_type,
            passed=passed,
            score=1.0 if passed else 0.0,
            message="" if passed else f"Turns {turns} >= max {assertion.max_turns}",
        )

    # Should never reach here with discriminated union
    logger.error("Unknown assertion type: %s", assertion_type)
    return AssertionResult(
        type=assertion_type,
        passed=False,
        score=0.0,
        message=f"Unknown assertion type: {assertion_type}",
    )
