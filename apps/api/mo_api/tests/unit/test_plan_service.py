"""PlanService 边界守卫单测。"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from mo_api.models.enums import TaskStatus
from mo_api.services.plan_service import PlanService
from mo_api.services.state_machine import InvalidTransitionError
from mo_api.storage.tables import TaskTable


def test_transition_task_checks_actual_persisted_source(engine) -> None:
    with Session(engine) as session:
        session.add(
            TaskTable(
                id="task-1",
                goal="x",
                repo_urls=["https://github.com/owner/repo"],
                paper_urls=[],
                output_language="zh",
                permissions={},
                status=TaskStatus.WAITING_USER_APPROVAL.value,
            )
        )
        session.commit()

        service = PlanService(session, graph=object())

        with pytest.raises(InvalidTransitionError, match="expected PLANNING"):
            service._transition_task(
                "task-1",
                TaskStatus.PLANNING,
                TaskStatus.WAITING_USER_APPROVAL,
            )

        row = session.get(TaskTable, "task-1")
        assert row is not None
        assert row.status == TaskStatus.WAITING_USER_APPROVAL.value
