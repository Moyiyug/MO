"""数据访问层（Repository）。

负责 TaskTable（DB 行）与 TaskResponse（API 模型）之间的映射。
上层 service 不直接接触 SQLModel 会话之外的 ORM 细节。
"""

from __future__ import annotations

from sqlmodel import Session, select

from ..models.enums import OutputLanguage, TaskStatus
from ..models.plan import Plan
from ..models.task import TaskPermissions, TaskResponse
from .tables import PlanTable, TaskTable


def _to_response(row: TaskTable) -> TaskResponse:
    return TaskResponse(
        task_id=row.id,
        goal=row.goal,
        status=TaskStatus(row.status),
        repo_urls=list(row.repo_urls or []),
        paper_urls=list(row.paper_urls or []),
        output_language=OutputLanguage(row.output_language),
        template=row.template,
        permissions=TaskPermissions(**(row.permissions or {})),
        created_at=row.created_at,
    )


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, row: TaskTable) -> TaskResponse:
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_response(row)

    def list(self) -> list[TaskResponse]:
        rows = self.session.exec(
            select(TaskTable).order_by(TaskTable.created_at.desc())
        ).all()
        return [_to_response(r) for r in rows]

    def get(self, task_id: str) -> TaskResponse | None:
        row = self.session.get(TaskTable, task_id)
        return _to_response(row) if row else None

    def update_status(self, task_id: str, status: TaskStatus) -> TaskResponse | None:
        row = self.session.get(TaskTable, task_id)
        if row is None:
            return None
        row.status = status.value
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_response(row)


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count_by_task(self, task_id: str) -> int:
        rows = self.session.exec(
            select(PlanTable).where(PlanTable.task_id == task_id)
        ).all()
        return len(rows)

    def create(
        self,
        *,
        plan: Plan,
        version: int,
        thread_id: str,
        approved: bool = False,
    ) -> Plan:
        row = PlanTable(
            id=plan.id,
            task_id=plan.task_id,
            version=version,
            thread_id=thread_id,
            plan_data=plan.model_dump(mode="json"),
            approved=approved,
            created_at=plan.created_at,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Plan.model_validate(row.plan_data)

    def get_latest_by_task(self, task_id: str) -> Plan | None:
        row = self.session.exec(
            select(PlanTable)
            .where(PlanTable.task_id == task_id)
            .order_by(PlanTable.version.desc())
        ).first()
        if row is None:
            return None
        return Plan.model_validate(row.plan_data)

    def get_latest_row(self, task_id: str) -> PlanTable | None:
        return self.session.exec(
            select(PlanTable)
            .where(PlanTable.task_id == task_id)
            .order_by(PlanTable.version.desc())
        ).first()

    def update_plan_data(self, plan_id: str, plan_data: dict, *, approved: bool) -> Plan | None:
        row = self.session.get(PlanTable, plan_id)
        if row is None:
            return None
        row.plan_data = plan_data
        row.approved = approved
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Plan.model_validate(row.plan_data)
