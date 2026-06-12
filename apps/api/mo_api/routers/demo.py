"""DemoMode 路由（F-014）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..models.task import TaskCreateResponse
from ..services.demo_service import DemoService
from ..storage.db import get_session

router = APIRouter(prefix="/api/demo", tags=["demo"])


def get_demo_service(session: Session = Depends(get_session)) -> DemoService:
    return DemoService(session)


@router.post("/seed", response_model=TaskCreateResponse)
def seed_demo(
    service: DemoService = Depends(get_demo_service),
) -> TaskCreateResponse:
    """写入/刷新离线 demo 任务数据。"""
    return service.seed_demo_task()
