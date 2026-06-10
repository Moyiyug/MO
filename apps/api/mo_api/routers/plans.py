"""PlanMode 路由（PRD F-002 / F-003 / §5）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..models.plan import (
    ApprovePlanRequest,
    ApprovePlanResponse,
    ClarificationsRequest,
    PlanResponse,
    ReplanRequest,
)
from ..services.plan_service import (
    PlanConflictError,
    PlanNotFoundError,
    PlanService,
)
from ..services.state_machine import InvalidTransitionError
from ..services.task_service import TaskNotFoundError
from ..storage.db import get_session
from ..workflows.graph import get_plan_graph

router = APIRouter(prefix="/api/tasks", tags=["plans"])


def get_plan_service(session: Session = Depends(get_session)) -> PlanService:
    return PlanService(session, graph=get_plan_graph())


@router.post("/{task_id}/plan", response_model=PlanResponse)
def generate_plan(
    task_id: str,
    service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        return service.generate(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=409, detail="plan not found") from exc
    except PlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{task_id}/plan", response_model=PlanResponse)
def get_plan(
    task_id: str,
    service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        return service.get_latest_plan(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc


@router.post("/{task_id}/clarifications", response_model=PlanResponse)
def submit_clarifications(
    task_id: str,
    payload: ClarificationsRequest,
    service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        return service.submit_clarifications(task_id, payload)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=409, detail="plan not found") from exc
    except PlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/approve-plan", response_model=ApprovePlanResponse)
def approve_plan(
    task_id: str,
    payload: ApprovePlanRequest,
    service: PlanService = Depends(get_plan_service),
) -> ApprovePlanResponse:
    try:
        plan, task_status = service.approve(task_id, payload)
        return ApprovePlanResponse(plan=plan, status=task_status.value)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=409, detail="plan not found") from exc
    except PlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/replan", response_model=PlanResponse)
def replan(
    task_id: str,
    payload: ReplanRequest,
    service: PlanService = Depends(get_plan_service),
) -> PlanResponse:
    try:
        return service.replan(task_id, payload.reason)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
