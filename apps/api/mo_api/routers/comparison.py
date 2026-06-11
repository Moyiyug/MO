"""多仓库对比 API（PRD F-008 / §5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..models.comparison import ComparisonMatrix, RecomputeComparisonRequest
from ..models.enums import TaskStatus
from ..services.comparison_service import ComparisonService
from ..storage.db import get_session
from ..storage.repositories import RepoCardRepository, TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["comparison"])


def get_comparison_service(session: Session = Depends(get_session)) -> ComparisonService:
    return ComparisonService(session)


@router.get("/{task_id}/comparison", response_model=ComparisonMatrix)
def get_comparison(
    task_id: str,
    service: ComparisonService = Depends(get_comparison_service),
    session: Session = Depends(get_session),
) -> ComparisonMatrix:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    matrix = service.get_by_task(task_id)
    if matrix is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="comparison not found",
        )
    return matrix


@router.post("/{task_id}/comparison", response_model=ComparisonMatrix)
def recompute_comparison(
    task_id: str,
    body: RecomputeComparisonRequest,
    service: ComparisonService = Depends(get_comparison_service),
    session: Session = Depends(get_session),
) -> ComparisonMatrix:
    task = TaskRepository(session).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    allowed = {TaskStatus.REPORT_DRAFT, TaskStatus.REVIEW_REQUIRED, TaskStatus.DONE}
    if task.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"task status {task.status.value} does not allow comparison recompute",
        )
    repo_cards = RepoCardRepository(session).list_by_task(task_id)
    try:
        return service.recompute_weights(task_id, body.weights, repo_cards)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)[:200],
        ) from exc
