"""报告生成与导出 API（PRD F-011 / §5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from ..models.enums import TaskStatus
from ..models.report import Report
from ..models.task import TaskResponse
from ..services.report_service import ReportNotReadyError, ReportService
from ..storage.db import get_session
from ..storage.repositories import TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["report"])


def get_report_service(session: Session = Depends(get_session)) -> ReportService:
    return ReportService(session)


def _get_task_or_404(session: Session, task_id: str) -> TaskResponse:
    task = TaskRepository(session).get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return task


@router.get("/{task_id}/report", response_model=Report)
async def get_report(
    task_id: str,
    service: ReportService = Depends(get_report_service),
    session: Session = Depends(get_session),
) -> Report:
    """只读获取已缓存的报告。（F-013: GET 无副作用）"""
    _get_task_or_404(session, task_id)
    try:
        cached = service.get_cached_report(task_id)
    except ReportNotReadyError:
        cached = None
    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告尚未生成。请使用 POST /api/tasks/{task_id}/generate-report 生成。",
        )
    return cached


@router.post("/{task_id}/generate-report", response_model=Report)
async def generate_report(
    task_id: str,
    service: ReportService = Depends(get_report_service),
    session: Session = Depends(get_session),
) -> Report:
    """显式触发报告生成。（F-013）"""
    _get_task_or_404(session, task_id)
    try:
        return await service.generate_async(task_id)
    except ReportNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/{task_id}/export")
async def export_report(
    task_id: str,
    service: ReportService = Depends(get_report_service),
    session: Session = Depends(get_session),
) -> PlainTextResponse:
    _get_task_or_404(session, task_id)
    try:
        cached = service.get_cached_report(task_id)
    except ReportNotReadyError:
        cached = None
    if cached is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告尚未生成。请先生成报告。",
        )
    filename = f"mo-report-{task_id[:8]}.md"
    return PlainTextResponse(
        content=cached.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{task_id}/regenerate-report", response_model=Report)
async def regenerate_report(
    task_id: str,
    service: ReportService = Depends(get_report_service),
    session: Session = Depends(get_session),
) -> Report:
    _get_task_or_404(session, task_id)
    try:
        return await service.generate_async(task_id)
    except ReportNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/{task_id}/confirm-report")
def confirm_report(
    task_id: str,
    service: ReportService = Depends(get_report_service),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    _get_task_or_404(session, task_id)
    try:
        new_status = service.confirm_report(task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return {"task_id": task_id, "status": new_status.value}
