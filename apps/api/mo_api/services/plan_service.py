"""PlanMode 业务编排（M2 mock）。"""

from __future__ import annotations

from typing import Any

from langgraph.types import Command
from sqlmodel import Session

from ..models.enums import PlanStepStatus, TaskStatus
from ..models.plan import (
    ApprovePlanRequest,
    ClarificationsRequest,
    Plan,
)
from ..models.task import TaskResponse
from ..storage.repositories import PlanRepository, TaskRepository
from ..workflows.graph import get_plan_graph
from ..workflows.state import MOState
from .state_machine import InvalidTransitionError, ensure_transition
from .task_service import TaskNotFoundError


class PlanNotFoundError(Exception):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"plan not found for task: {task_id}")


class PlanConflictError(Exception):
    """计划状态冲突（如无计划即批准、重复批准）。"""


def _has_unanswered_required(plan: Plan) -> bool:
    return any(q.required and not q.answer for q in plan.clarifying_questions)


def _validate_required_clarification_answers(
    plan: Plan, answers: dict[str, str]
) -> None:
    question_ids = {q.id for q in plan.clarifying_questions}
    unknown_ids = sorted(set(answers) - question_ids)
    if unknown_ids:
        raise PlanConflictError(
            f"unknown clarification question_id(s): {', '.join(unknown_ids)}"
        )

    missing_required = sorted(
        q.id for q in plan.clarifying_questions if q.required and not q.answer and q.id not in answers
    )
    if missing_required:
        raise PlanConflictError(
            f"missing required clarification answer(s): {', '.join(missing_required)}"
        )


def _thread_config(task_id: str, version: int) -> dict[str, Any]:
    return {"configurable": {"thread_id": f"{task_id}:v{version}"}}


class PlanService:
    def __init__(self, session: Session, graph: Any | None = None) -> None:
        self.session = session
        self.task_repo = TaskRepository(session)
        self.plan_repo = PlanRepository(session)
        self.graph = graph or get_plan_graph()

    def _get_task_or_404(self, task_id: str) -> TaskResponse:
        task = self.task_repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def _transition_task(self, task_id: str, src: TaskStatus, dst: TaskStatus) -> TaskResponse:
        current = self._get_task_or_404(task_id).status
        if current != src:
            raise InvalidTransitionError(
                f"illegal transition source: expected {src.value}, got {current.value}"
            )
        ensure_transition(current, dst)
        updated = self.task_repo.update_status(task_id, dst)
        if updated is None:
            raise TaskNotFoundError(task_id)
        return updated

    def _build_initial_state(
        self,
        task: TaskResponse,
        clarification_answers: dict[str, str] | None = None,
    ) -> MOState:
        return {
            "task_id": task.task_id,
            "goal": task.goal,
            "repo_urls": task.repo_urls,
            "paper_urls": task.paper_urls,
            "output_language": task.output_language.value,
            "template": task.template,
            "permissions": task.permissions.model_dump(),
            "clarification_answers": clarification_answers or {},
        }

    def _run_plan_graph_until_interrupt(
        self, initial_state: MOState, config: dict[str, Any]
    ) -> Plan:
        self.graph.invoke(initial_state, config)
        snapshot = self.graph.get_state(config)
        plan_dict = snapshot.values.get("plan")
        if not plan_dict:
            raise PlanConflictError("plan generation failed: empty plan in graph state")
        return Plan.model_validate(plan_dict)

    def generate(self, task_id: str) -> Plan:
        task = self._get_task_or_404(task_id)
        current = task.status

        if current not in {
            TaskStatus.PLANNING,
            TaskStatus.WAITING_USER_CLARIFICATION,
            TaskStatus.REPLANNING,
            TaskStatus.WAITING_USER_APPROVAL,
        }:
            raise InvalidTransitionError(
                f"cannot generate plan from status {current.value}"
            )

        if current is TaskStatus.WAITING_USER_APPROVAL:
            self._transition_task(task_id, current, TaskStatus.PLANNING)
            current = TaskStatus.PLANNING

        version = self.plan_repo.count_by_task(task_id) + 1
        config = _thread_config(task_id, version)
        initial = self._build_initial_state(task)
        plan = self._run_plan_graph_until_interrupt(initial, config)
        saved = self.plan_repo.create(
            plan=plan, version=version, thread_id=config["configurable"]["thread_id"]
        )

        if _has_unanswered_required(saved):
            if current is not TaskStatus.WAITING_USER_CLARIFICATION:
                self._transition_task(
                    task_id, current, TaskStatus.WAITING_USER_CLARIFICATION
                )
        elif current is TaskStatus.REPLANNING:
            self._transition_task(task_id, current, TaskStatus.WAITING_USER_APPROVAL)
        elif current is TaskStatus.PLANNING:
            self._transition_task(task_id, current, TaskStatus.WAITING_USER_APPROVAL)
        elif current is TaskStatus.WAITING_USER_CLARIFICATION:
            self._transition_task(
                task_id, current, TaskStatus.WAITING_USER_APPROVAL
            )

        return saved

    def submit_clarifications(
        self, task_id: str, payload: ClarificationsRequest
    ) -> Plan:
        task = self._get_task_or_404(task_id)
        if task.status not in {
            TaskStatus.WAITING_USER_CLARIFICATION,
            TaskStatus.WAITING_USER_APPROVAL,
        }:
            raise InvalidTransitionError(
                f"cannot submit clarifications from status {task.status.value}"
            )

        answers = {a.question_id: a.answer for a in payload.answers}
        latest_plan = self.plan_repo.get_latest_by_task(task_id)
        if latest_plan is None:
            raise PlanNotFoundError(task_id)
        _validate_required_clarification_answers(latest_plan, answers)

        if task.status is TaskStatus.WAITING_USER_CLARIFICATION:
            self._transition_task(
                task_id, TaskStatus.WAITING_USER_CLARIFICATION, TaskStatus.PLANNING
            )
            task = self._get_task_or_404(task_id)
        elif task.status is TaskStatus.WAITING_USER_APPROVAL:
            self._transition_task(
                task_id, TaskStatus.WAITING_USER_APPROVAL, TaskStatus.PLANNING
            )
            task = self._get_task_or_404(task_id)

        version = self.plan_repo.count_by_task(task_id) + 1
        config = _thread_config(task_id, version)
        initial = self._build_initial_state(task, clarification_answers=answers)
        plan = self._run_plan_graph_until_interrupt(initial, config)
        self._transition_task(task_id, TaskStatus.PLANNING, TaskStatus.WAITING_USER_APPROVAL)

        return self.plan_repo.create(
            plan=plan, version=version, thread_id=config["configurable"]["thread_id"]
        )

    def approve(self, task_id: str, edits: ApprovePlanRequest) -> tuple[Plan, TaskStatus]:
        task = self._get_task_or_404(task_id)

        if task.status is TaskStatus.PLAN_APPROVED:
            raise PlanConflictError("plan already approved")

        if task.status is not TaskStatus.WAITING_USER_APPROVAL:
            raise InvalidTransitionError(
                f"cannot approve plan from status {task.status.value}"
            )

        latest_row = self.plan_repo.get_latest_row(task_id)
        if latest_row is None:
            raise PlanNotFoundError(task_id)

        config = {"configurable": {"thread_id": latest_row.thread_id}}
        self.graph.invoke(Command(resume={"approved": True}), config)

        plan = Plan.model_validate(latest_row.plan_data)

        if edits.rubric_weights:
            plan.report_rubric.weights = edits.rubric_weights

        if edits.disabled_step_ids:
            disabled = set(edits.disabled_step_ids)
            for step in plan.proposed_steps:
                if step.id in disabled:
                    step.status = PlanStepStatus.SKIPPED

        plan = self.plan_repo.update_plan_data(
            plan.id, plan.model_dump(mode="json"), approved=True
        )
        assert plan is not None

        updated_task = self._transition_task(
            task_id, TaskStatus.WAITING_USER_APPROVAL, TaskStatus.PLAN_APPROVED
        )
        return plan, updated_task.status

    def replan(self, task_id: str, reason: str | None = None) -> Plan:
        task = self._get_task_or_404(task_id)
        current = task.status

        if current not in {
            TaskStatus.WAITING_USER_APPROVAL,
            TaskStatus.PLAN_APPROVED,
            TaskStatus.EXECUTING,
        }:
            raise InvalidTransitionError(f"cannot replan from status {current.value}")

        self._transition_task(task_id, current, TaskStatus.REPLANNING)
        return self.generate(task_id)

    def get_latest_plan(self, task_id: str) -> Plan:
        self._get_task_or_404(task_id)
        plan = self.plan_repo.get_latest_by_task(task_id)
        if plan is None:
            raise PlanNotFoundError(task_id)
        return plan
