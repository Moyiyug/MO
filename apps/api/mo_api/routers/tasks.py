"""任务路由（PRD §5）。

路由层只做 I/O 与依赖装配，业务委托 TaskService。
请求校验由 Pydantic 模型完成；非法 body 由 FastAPI 返回 422。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from ..models.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskBulkDeleteResponse,
    TaskPageResponse,
    TaskResponse,
)
from ..services.task_service import (
    TaskDeleteConflictError,
    TaskNotFoundError,
    TaskService,
)
from ..storage.db import get_session

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_service(session: Session = Depends(get_session)) -> TaskService:
    return TaskService(session)


@router.post(
    "",
    response_model=TaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: TaskCreateRequest,
    service: TaskService = Depends(get_task_service),
) -> TaskCreateResponse:
    task = service.create_task(payload)
    return TaskCreateResponse(task_id=task.task_id, status=task.status)


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    service: TaskService = Depends(get_task_service),
) -> list[TaskResponse]:
    return service.list_tasks()


@router.get("/page", response_model=TaskPageResponse)
def page_tasks(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: TaskService = Depends(get_task_service),
) -> TaskPageResponse:
    return service.page_tasks(limit=limit, offset=offset)


@router.delete("", response_model=TaskBulkDeleteResponse)
def delete_all_tasks(
    service: TaskService = Depends(get_task_service),
) -> TaskBulkDeleteResponse:
    """删除所有可删除历史任务；EXECUTING 任务会跳过（F-013）。"""
    return service.delete_all_deletable_tasks()


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskResponse:
    try:
        return service.get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        ) from exc


@router.post(
    "/{task_id}/rerun",
    response_model=TaskCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def rerun_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> TaskCreateResponse:
    """克隆任务输入为新任务并重进 PlanMode（F-013）。"""
    try:
        task = service.clone_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        ) from exc
    return TaskCreateResponse(task_id=task.task_id, status=task.status)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    service: TaskService = Depends(get_task_service),
) -> None:
    """删除历史任务及本地 task 级存储（F-013）。"""
    try:
        service.delete_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="task not found",
        ) from exc
    except TaskDeleteConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cannot delete executing task",
        ) from exc
