"""plan_builder 规则 mock 单测。"""

from __future__ import annotations

from mo_api.models.enums import PlanStepTool
from mo_api.workflows.nodes.plan_builder import build_plan_from_state


def _state(**overrides):
    base = {
        "task_id": "t1",
        "goal": "对比 RAG 框架",
        "repo_urls": [
            "https://github.com/a/r1",
            "https://github.com/b/r2",
        ],
        "paper_urls": [],
        "output_language": "zh",
        "permissions": {
            "allow_repo_clone": True,
            "allow_web_search": False,
            "allow_smoke_test": False,
        },
        "clarification_answers": {},
    }
    base.update(overrides)
    return base


def test_plan_has_required_fields() -> None:
    plan = build_plan_from_state(_state())
    assert plan.task_summary
    assert plan.confirmed_context
    assert plan.unknowns
    assert plan.clarifying_questions
    assert plan.proposed_steps
    assert plan.report_rubric.weights
    assert plan.risk_summary
    assert plan.approval_required is True


def test_multi_repo_has_comparison_step() -> None:
    plan = build_plan_from_state(_state())
    tools = {s.tool for s in plan.proposed_steps}
    assert PlanStepTool.COMPARISON in tools


def test_single_repo_no_comparison_step() -> None:
    plan = build_plan_from_state(
        _state(repo_urls=["https://github.com/a/r1"])
    )
    tools = {s.tool for s in plan.proposed_steps}
    assert PlanStepTool.COMPARISON not in tools


def test_rubric_weights_sum_to_one() -> None:
    plan = build_plan_from_state(_state())
    total = sum(plan.report_rubric.weights.values())
    assert abs(total - 1.0) < 0.01


def test_repo_clone_disabled_requires_approval() -> None:
    plan = build_plan_from_state(
        _state(permissions={"allow_repo_clone": False, "allow_web_search": False})
    )
    repo_step = next(
        s for s in plan.proposed_steps if s.tool is PlanStepTool.REPO_INGEST
    )
    assert repo_step.requires_approval is True


def test_report_writer_requires_approval() -> None:
    plan = build_plan_from_state(_state())
    report_step = next(
        s for s in plan.proposed_steps if s.tool is PlanStepTool.REPORT_WRITER
    )
    assert report_step.requires_approval is True


def test_clarification_answer_removes_required_question() -> None:
    plan = build_plan_from_state(
        _state(clarification_answers={"comparison_focus": "可复现性"})
    )
    assert not any(
        q.id == "comparison_focus" and q.required and not q.answer
        for q in plan.clarifying_questions
    )
