"""SSE 事件流与执行控制路由（PRD F-010）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from ..models.events import (
    ExecuteResponse,
    StepApproveRequest,
    StepApproveResponse,
)
from ..services.event_bus import EventBus, get_event_bus
from ..services.execution_service import (
    ExecutionConflictError,
    ExecutionService,
    get_execution_service,
)
from ..services.state_machine import InvalidTransitionError
from ..services.task_service import TaskNotFoundError
from ..storage.db import get_session
from ..storage.repositories import TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["events"])


def get_bus() -> EventBus:
    return get_event_bus()


def get_executor() -> ExecutionService:
    return get_execution_service()


async def _event_stream(
    task_id: str,
    since: int,
    bus: EventBus,
) -> AsyncIterator[dict[str, str]]:
    history = bus.list_since(task_id, since)
    last_seq = since
    for event in history:
        last_seq = event.seq
        yield {"event": "node", "data": event.model_dump_json()}

    queue = bus.subscribe(task_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            if event.seq > last_seq:
                last_seq = event.seq
                yield {"event": "node", "data": event.model_dump_json()}
    finally:
        bus.unsubscribe(task_id, queue)


@router.get("/{task_id}/events")
async def stream_events(
    task_id: str,
    request: Request,
    since: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    bus: EventBus = Depends(get_bus),
) -> EventSourceResponse:
    task = TaskRepository(session).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    async def generator() -> AsyncIterator[dict[str, str]]:
        async for item in _event_stream(task_id, since, bus):
            if await request.is_disconnected():
                break
            yield item

    return EventSourceResponse(generator())


@router.post("/{task_id}/execute", response_model=ExecuteResponse)
async def execute_task(
    task_id: str,
    session: Session = Depends(get_session),
    executor: ExecutionService = Depends(get_executor),
) -> ExecuteResponse:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    try:
        task_status = await executor.start(task_id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExecuteResponse(task_id=task_id, status=task_status.value)


@router.post(
    "/{task_id}/steps/{step_id}/approve",
    response_model=StepApproveResponse,
)
async def approve_step(
    task_id: str,
    step_id: str,
    payload: StepApproveRequest,
    session: Session = Depends(get_session),
    executor: ExecutionService = Depends(get_executor),
) -> StepApproveResponse:
    if TaskRepository(session).get(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    try:
        await executor.approve_step(task_id, step_id, payload.approved)
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    node_status = "completed" if payload.approved else "failed"
    return StepApproveResponse(
        task_id=task_id,
        step_id=step_id,
        status=node_status,
    )
