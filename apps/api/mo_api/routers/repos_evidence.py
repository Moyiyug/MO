"""仓库卡片与证据链 API（PRD §5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..models.evidence import EvidenceItem
from ..models.repo import RepoCard
from ..services.evidence_service import EvidenceService
from ..services.task_service import TaskNotFoundError, TaskService
from ..storage.db import get_session
from ..storage.repositories import RepoCardRepository, TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["repos", "evidence"])


def get_task_service(session: Session = Depends(get_session)) -> TaskService:
    return TaskService(session)


@router.get("/{task_id}/repos", response_model=list[RepoCard])
def list_repo_cards(
    task_id: str,
    session: Session = Depends(get_session),
) -> list[RepoCard]:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return RepoCardRepository(session).list_by_task(task_id)


@router.get("/{task_id}/evidence", response_model=list[EvidenceItem])
def list_evidence(
    task_id: str,
    session: Session = Depends(get_session),
) -> list[EvidenceItem]:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return EvidenceService(session).list_by_task(task_id)
