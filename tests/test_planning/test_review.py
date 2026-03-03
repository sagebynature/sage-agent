from __future__ import annotations


from sage.planning.review import LLMPlanReviewer, ReviewResult, review_loop
from sage.planning.state import PlanState, PlanTask


def _make_plan(n_tasks: int = 3) -> PlanState:
    return PlanState(
        plan_name="test-plan",
        description="a plan for testing",
        tasks=[PlanTask(description=f"task {i + 1}") for i in range(n_tasks)],
    )


class TestReviewResult:
    def test_defaults(self) -> None:
        r = ReviewResult(approved=True)
        assert r.feedback == []
        assert r.metadata == {}

    def test_with_feedback(self) -> None:
        r = ReviewResult(approved=False, feedback=["needs more detail"])
        assert len(r.feedback) == 1


class TestReviewLoop:
    async def test_immediate_approval(self) -> None:
        async def always_approve(plan: PlanState) -> ReviewResult:
            return ReviewResult(approved=True)

        plan = _make_plan()
        final, result = await review_loop(plan, always_approve, None, max_iterations=3)
        assert result.approved
        assert final.plan_name == "test-plan"

    async def test_reject_then_approve(self) -> None:
        call_count = 0

        async def reject_once(plan: PlanState) -> ReviewResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ReviewResult(approved=False, feedback=["too vague"])
            return ReviewResult(approved=True)

        async def noop_reviser(plan: PlanState, feedback: list[str]) -> PlanState:
            return plan

        plan = _make_plan()
        final, result = await review_loop(plan, reject_once, noop_reviser, max_iterations=5)
        assert result.approved
        assert call_count == 2

    async def test_always_reject_hits_max(self) -> None:
        async def always_reject(plan: PlanState) -> ReviewResult:
            return ReviewResult(approved=False, feedback=["nope"])

        async def noop_reviser(plan: PlanState, feedback: list[str]) -> PlanState:
            return plan

        plan = _make_plan()
        final, result = await review_loop(plan, always_reject, noop_reviser, max_iterations=3)
        assert not result.approved

    async def test_reviser_called_between_iterations(self) -> None:
        reviser_calls: list[list[str]] = []
        review_count = 0

        async def reject_twice(plan: PlanState) -> ReviewResult:
            nonlocal review_count
            review_count += 1
            if review_count <= 2:
                return ReviewResult(approved=False, feedback=[f"issue-{review_count}"])
            return ReviewResult(approved=True)

        async def tracking_reviser(plan: PlanState, feedback: list[str]) -> PlanState:
            reviser_calls.append(feedback)
            return plan

        plan = _make_plan()
        await review_loop(plan, reject_twice, tracking_reviser, max_iterations=5)
        assert len(reviser_calls) == 2
        assert reviser_calls[0] == ["issue-1"]
        assert reviser_calls[1] == ["issue-2"]


class TestLLMPlanReviewerParse:
    def test_parse_approved(self) -> None:
        text = "APPROVED: yes\nFEEDBACK:\n- none"
        result = LLMPlanReviewer._parse_response(text)
        assert result.approved
        assert result.feedback == []

    def test_parse_rejected_with_feedback(self) -> None:
        text = "APPROVED: no\nFEEDBACK:\n- task 1 is vague\n- missing tests"
        result = LLMPlanReviewer._parse_response(text)
        assert not result.approved
        assert result.feedback == ["task 1 is vague", "missing tests"]

    def test_parse_true_variant(self) -> None:
        text = "APPROVED: true\nFEEDBACK:\n- none"
        result = LLMPlanReviewer._parse_response(text)
        assert result.approved

    def test_parse_case_insensitive(self) -> None:
        text = "approved: YES\nFEEDBACK:\n- none"
        result = LLMPlanReviewer._parse_response(text)
        assert result.approved

    def test_parse_no_feedback_lines(self) -> None:
        text = "APPROVED: no"
        result = LLMPlanReviewer._parse_response(text)
        assert not result.approved
        assert result.feedback == []
