"""任务状态机单测（PRD §4）。"""

from __future__ import annotations

import pytest

from mo_api.models.enums import TaskStatus
from mo_api.services.state_machine import (
    InvalidTransitionError,
    can_transition,
    ensure_transition,
)


def test_created_to_planning_allowed() -> None:
    assert can_transition(TaskStatus.CREATED, TaskStatus.PLANNING) is True


def test_planning_to_approval_allowed() -> None:
    assert can_transition(
        TaskStatus.PLANNING, TaskStatus.WAITING_USER_APPROVAL
    ) is True


def test_any_to_failed_allowed() -> None:
    assert can_transition(TaskStatus.PLANNING, TaskStatus.FAILED) is True
    assert can_transition(TaskStatus.EXECUTING, TaskStatus.FAILED) is True


def test_illegal_transition_rejected() -> None:
    assert can_transition(TaskStatus.CREATED, TaskStatus.DONE) is False
    assert can_transition(TaskStatus.DONE, TaskStatus.EXECUTING) is False


def test_ensure_transition_raises_on_illegal() -> None:
    with pytest.raises(InvalidTransitionError):
        ensure_transition(TaskStatus.CREATED, TaskStatus.EXECUTING)


def test_ensure_transition_ok() -> None:
    ensure_transition(TaskStatus.CREATED, TaskStatus.PLANNING)


def test_m2_waiting_approval_to_plan_approved() -> None:
    assert can_transition(
        TaskStatus.WAITING_USER_APPROVAL, TaskStatus.PLAN_APPROVED
    )


def test_m2_waiting_approval_to_replanning() -> None:
    assert can_transition(
        TaskStatus.WAITING_USER_APPROVAL, TaskStatus.REPLANNING
    )


def test_m2_plan_approved_to_replanning() -> None:
    assert can_transition(TaskStatus.PLAN_APPROVED, TaskStatus.REPLANNING)


def test_m2_cannot_skip_approval_to_executing() -> None:
    assert can_transition(
        TaskStatus.WAITING_USER_APPROVAL, TaskStatus.EXECUTING
    ) is False


def test_failed_can_return_to_plan_mode() -> None:
    assert can_transition(TaskStatus.FAILED, TaskStatus.PLANNING) is True
    assert can_transition(TaskStatus.FAILED, TaskStatus.REPLANNING) is True


def test_post_report_can_return_to_plan_mode() -> None:
    assert can_transition(TaskStatus.REVIEW_REQUIRED, TaskStatus.PLANNING) is True
    assert can_transition(TaskStatus.REPORT_DRAFT, TaskStatus.PLANNING) is True
    assert can_transition(TaskStatus.DONE, TaskStatus.PLANNING) is True
