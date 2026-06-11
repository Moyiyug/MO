"""论文调研与复现评估 API（PRD F-006 / F-007）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..models.reproducibility import ReproducibilityReport
from ..storage.db import get_session
from ..storage.repositories import ReproducibilityRepository, TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["research"])


@router.get("/{task_id}/reproducibility", response_model=ReproducibilityReport)
def get_reproducibility(
    task_id: str,
    session: Session = Depends(get_session),
) -> ReproducibilityReport:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    report = ReproducibilityRepository(session).get_by_task(task_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="reproducibility report not found",
        )
    return report
