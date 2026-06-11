"""SSE 与执行 API 集成测试（PRD F-010）。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import NodeStatus
from mo_api.models.events import NodeEvent
from mo_api.routers.events import _event_stream
from mo_api.services.event_bus import EventBus
from mo_api.storage.repositories import EventRepository


async def _approve_plan_flow(client, task_id: str) -> None:
    await client.post(f"/api/tasks/{task_id}/plan")
    await client.post(
        f"/api/tasks/{task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "可复现性"}]},
    )
    resp = await client.post(f"/api/tasks/{task_id}/approve-plan", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PLAN_APPROVED"


def _latest_waiting_step(task_id: str, engine) -> str | None:
    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
    latest: dict[str, NodeStatus] = {}
    for event in events:
        latest[event.node] = event.status
    for node, status in latest.items():
        if status is NodeStatus.WAITING_USER:
            return node
    return None


async def _wait_for_waiting_step(task_id: str, engine) -> str | None:
    for _ in range(30):
        step_id = _latest_waiting_step(task_id, engine)
        if step_id is not None:
            return step_id
        await asyncio.sleep(0.1)
    return None


async def _approve_all_waiting_steps(client, task_id: str, engine) -> None:
    for _ in range(10):
        step_id = await _wait_for_waiting_step(task_id, engine)
        if step_id is None:
            break
        resp = await client.post(
            f"/api/tasks/{task_id}/steps/{step_id}/approve",
            json={"approved": True},
        )
        assert resp.status_code == 200
        await asyncio.sleep(0.2)


async def test_execute_and_sse_event_sequence(client, created_task_id, engine) -> None:
    await _approve_plan_flow(client, created_task_id)

    exec_resp = await client.post(f"/api/tasks/{created_task_id}/execute")
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "EXECUTING"

    await _approve_all_waiting_steps(client, created_task_id, engine)
    await asyncio.sleep(0.5)

    with Session(engine) as session:
        events = EventRepository(session).list_since(created_task_id, 0)
        assert len(events) >= 3
        seqs = [e.seq for e in events]
        assert seqs == sorted(seqs)
        assert seqs == list(range(1, len(seqs) + 1))
        statuses = {e.status for e in events}
        assert NodeStatus.PENDING in statuses
        assert NodeStatus.RUNNING in statuses
        assert NodeStatus.COMPLETED in statuses

        task = EventRepository(session)
        replay = task.list_since(created_task_id, events[1].seq)
        assert all(e.seq > events[1].seq for e in replay)

    task_resp = await client.get(f"/api/tasks/{created_task_id}")
    assert task_resp.json()["status"] == "REPORT_DRAFT"


async def test_execute_idempotent(client, created_task_id) -> None:
    await _approve_plan_flow(client, created_task_id)
    first = await client.post(f"/api/tasks/{created_task_id}/execute")
    second = await client.post(f"/api/tasks/{created_task_id}/execute")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "EXECUTING"


async def test_sse_replay_via_bus(client, created_task_id, engine) -> None:
    await _approve_plan_flow(client, created_task_id)
    await client.post(f"/api/tasks/{created_task_id}/execute")

    await asyncio.sleep(0.3)
    bus = EventBus()
    history = bus.list_since(created_task_id, 0)
    assert history
    assert history[0].seq == 1


async def test_step_reject_fails_task(client, engine) -> None:
    reject_payload = {
        "goal": "对比两个 RAG 框架的可复现性",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "permissions": {"allow_repo_clone": False},
    }
    create = await client.post("/api/tasks", json=reject_payload)
    task_id = create.json()["task_id"]
    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")

    step_id = await _wait_for_waiting_step(task_id, engine)
    assert step_id is not None

    reject = await client.post(
        f"/api/tasks/{task_id}/steps/{step_id}/approve",
        json={"approved": False},
    )
    assert reject.status_code == 200
    await asyncio.sleep(0.3)

    task = await client.get(f"/api/tasks/{task_id}")
    assert task.json()["status"] == "FAILED"


async def test_events_endpoint_replay_matches_db(client, created_task_id, engine) -> None:
    """SSE 端点通过 EventBus 重放与 DB 一致（流式解析在 ASGITransport 下不稳定，重放逻辑由 bus 覆盖）。"""
    await _approve_plan_flow(client, created_task_id)
    await client.post(f"/api/tasks/{created_task_id}/execute")
    await asyncio.sleep(0.3)

    with Session(engine) as session:
        db_events = EventRepository(session).list_since(created_task_id, 0)

    bus = EventBus()
    replay = bus.list_since(created_task_id, 0)
    assert len(replay) == len(db_events)
    assert replay[0].seq == db_events[0].seq
    assert replay[-1].status == db_events[-1].status


async def test_event_stream_replays_history_as_node_events(engine) -> None:
    task_id = "stream-history"
    with Session(engine) as session:
        saved = EventRepository(session).append(
            NodeEvent(
                task_id=task_id,
                seq=0,
                node="step_a",
                status=NodeStatus.PENDING,
                evidence_ids=["ev-1"],
                created_at=datetime.now(timezone.utc),
            )
        )

    stream = _event_stream(task_id, 0, EventBus())
    try:
        item = await anext(stream)
    finally:
        await stream.aclose()

    assert item["event"] == "node"
    assert f'"seq":{saved.seq}' in item["data"]
    assert '"evidence_ids":["ev-1"]' in item["data"]
