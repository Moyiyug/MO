"""任务业务服务。

负责创建/查询任务。创建时按 PRD F-001 直接置为 PLANNING（CREATED -> PLANNING），
且 MUST NOT 执行任何脚本 / 触发副作用。
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import uuid
from pathlib import Path
from collections.abc import Iterable

from langgraph.checkpoint.sqlite import SqliteSaver
from sqlmodel import Session

from ..config import Settings, get_settings
from ..models.enums import TaskStatus
from ..models.task import (
    TaskBulkDeleteResponse,
    TaskCreateRequest,
    TaskPageResponse,
    TaskPermissions,
    TaskResponse,
)
from ..storage.repositories import TaskRepository
from ..storage.tables import TaskTable
from .state_machine import ensure_transition

logger = logging.getLogger("mo_api.task_service")


class TaskNotFoundError(Exception):
    """任务不存在。"""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"task not found: {task_id}")


class TaskDeleteConflictError(Exception):
    """任务当前状态不允许删除。"""


def _remove_task_child_dir(base_dir: str, task_id: str) -> None:
    """删除 base_dir/task_id，并确保最终路径仍在 base_dir 内。"""
    base = Path(base_dir).resolve()
    target = (base / task_id).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise RuntimeError("refusing to delete path outside configured base") from exc
    if target == base:
        raise RuntimeError("refusing to delete configured base directory")
    if target.exists():
        shutil.rmtree(target)


def _delete_checkpoint_threads(db_path: str, thread_ids: Iterable[str]) -> None:
    unique_ids = [thread_id for thread_id in dict.fromkeys(thread_ids) if thread_id]
    if not unique_ids:
        return
    path = Path(db_path)
    if not path.exists():
        return
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        saver = SqliteSaver(conn)
        saver.setup()
        for thread_id in unique_ids:
            saver.delete_thread(thread_id)
    finally:
        conn.close()


def cleanup_deleted_task_runtime(
    task_id: str, plan_thread_ids: list[str], settings: Settings | None = None
) -> None:
    """清理已删除任务的本地运行时产物（幂等、按 task_id 隔离）。"""
    settings = settings or get_settings()
    _delete_checkpoint_threads(settings.checkpoint_db_path, plan_thread_ids)
    _delete_checkpoint_threads(
        settings.execute_checkpoint_db_path, [f"exec:{task_id}"]
    )
    for base_dir in (
        settings.chroma_index_dir,
        settings.paper_index_dir,
        settings.sandbox_workdir_base,
    ):
        _remove_task_child_dir(base_dir, task_id)


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

    def page_tasks(self, *, limit: int, offset: int) -> TaskPageResponse:
        return TaskPageResponse(
            items=self.repo.page(limit=limit, offset=offset),
            total=self.repo.count(),
            limit=limit,
            offset=offset,
        )

    def get_task(self, task_id: str) -> TaskResponse:
        task = self.repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def clone_task(self, task_id: str) -> TaskResponse:
        """克隆已有任务输入为新任务（F-013 rerun）。

        复制 goal/repos/papers/permissions 等，新任务进入 PLANNING，不触发副作用。
        """
        source = self.repo.get(task_id)
        if source is None:
            raise TaskNotFoundError(task_id)

        permissions = TaskPermissions(**source.permissions.model_dump())
        # 重置高风险权限：rerun 需用户在新任务中重新授权（R-004）
        permissions.allow_web_search = False
        permissions.allow_smoke_test = False
        permissions.allow_dependency_install = False
        payload = TaskCreateRequest(
            goal=source.goal,
            repo_urls=list(source.repo_urls),
            paper_urls=list(source.paper_urls),
            output_language=source.output_language,
            template=source.template,
            permissions=permissions,
        )
        return self.create_task(payload)

    def delete_task(self, task_id: str) -> None:
        """硬删除历史任务及本地 task 级产物（F-013）。

        当前没有取消执行机制，所以 EXECUTING 任务不允许删除，避免后台图继续写入。
        """
        task = self.repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        if task.status is TaskStatus.EXECUTING:
            raise TaskDeleteConflictError("cannot delete executing task")

        plan_thread_ids = self.repo.delete_bundle(task_id)
        if plan_thread_ids is None:
            raise TaskNotFoundError(task_id)

        try:
            cleanup_deleted_task_runtime(task_id, plan_thread_ids)
        except Exception:
            logger.exception("task runtime cleanup failed for deleted task %s", task_id)
            raise

    def delete_all_deletable_tasks(self) -> TaskBulkDeleteResponse:
        """删除所有非执行中的历史任务，跳过 EXECUTING 任务（F-013）。"""
        deleted_task_ids: list[str] = []
        skipped_task_ids: list[str] = []

        for task in self.repo.list():
            if task.status is TaskStatus.EXECUTING:
                skipped_task_ids.append(task.task_id)
                continue
            self.delete_task(task.task_id)
            deleted_task_ids.append(task.task_id)

        return TaskBulkDeleteResponse(
            deleted_task_ids=deleted_task_ids,
            skipped_task_ids=skipped_task_ids,
        )
