"""任务业务服务。

负责创建/查询任务。创建时按 PRD F-001 直接置为 PLANNING（CREATED -> PLANNING），
且 MUST NOT 执行任何脚本 / 触发副作用。
"""

from __future__ import annotations

import uuid

from sqlmodel import Session

from ..models.enums import TaskStatus
from ..models.task import TaskCreateRequest, TaskResponse
from ..storage.repositories import TaskRepository
from ..storage.tables import TaskTable
from .state_machine import ensure_transition


class TaskNotFoundError(Exception):
    """任务不存在。"""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"task not found: {task_id}")


class TaskService:
    def __init__(self, session: Session) -> None:
        self.repo = TaskRepository(session)

    def create_task(self, payload: TaskCreateRequest) -> TaskResponse:
        # 创建即从 CREATED 迁移到 PLANNING（用状态机校验，保持一致性）
        ensure_transition(TaskStatus.CREATED, TaskStatus.PLANNING)

        row = TaskTable(
            id=uuid.uuid4().hex,
            goal=payload.goal,
            repo_urls=payload.repo_urls,
            paper_urls=payload.paper_urls,
            output_language=payload.output_language.value,
            template=payload.template,
            permissions=payload.permissions.model_dump(),
            status=TaskStatus.PLANNING.value,
        )
        return self.repo.create(row)

    def list_tasks(self) -> list[TaskResponse]:
        return self.repo.list()

    def get_task(self, task_id: str) -> TaskResponse:
        task = self.repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task
