"""任务路由（PRD §5）。

路由层只做 I/O 与依赖装配，业务委托 TaskService。
请求校验由 Pydantic 模型完成；非法 body 由 FastAPI 返回 422。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..models.task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskResponse,
)
from ..services.task_service import TaskNotFoundError, TaskService
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
