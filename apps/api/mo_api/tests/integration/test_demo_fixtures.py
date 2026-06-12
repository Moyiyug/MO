"""DemoMode 集成测试（F-014）。"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from mo_api.demo.fixtures import DEMO_TASK_ID
from mo_api.models.enums import TaskStatus
from mo_api.services.demo_service import DemoService
from mo_api.storage.repositories import (
    ComparisonRepository,
    EventRepository,
    EvidenceRepository,
    ReportRepository,
    TaskRepository,
)


@pytest.mark.asyncio
async def test_seed_demo_offline_readable(client, engine) -> None:
    with Session(engine) as session:
        resp = DemoService(session).seed_demo_task()
        assert resp.task_id == DEMO_TASK_ID
        assert resp.status is TaskStatus.DONE

    r = await client.get(f"/api/tasks/{DEMO_TASK_ID}")
    assert r.status_code == 200
    assert r.json()["status"] == "DONE"

    report = await client.get(f"/api/tasks/{DEMO_TASK_ID}/report")
    assert report.status_code == 200
    assert report.json()["task_id"] == DEMO_TASK_ID
    assert report.json()["markdown"]

    comparison = await client.get(f"/api/tasks/{DEMO_TASK_ID}/comparison")
    assert comparison.status_code == 200
    assert len(comparison.json()["repo_urls"]) == 2

    evidence = await client.get(f"/api/tasks/{DEMO_TASK_ID}/evidence")
    assert evidence.status_code == 200
    assert len(evidence.json()) >= 5

    with Session(engine) as session:
        events = EventRepository(session).list_since(DEMO_TASK_ID, 0)
        assert len(events) >= 1


@pytest.mark.asyncio
async def test_demo_seed_endpoint_idempotent(client) -> None:
    r1 = await client.post("/api/demo/seed")
    assert r1.status_code == 200
    r2 = await client.post("/api/demo/seed")
    assert r2.status_code == 200
    assert r1.json()["task_id"] == r2.json()["task_id"] == DEMO_TASK_ID


@pytest.mark.asyncio
async def test_task_rerun_clones_new_task(client, created_task_id) -> None:
    r = await client.post(f"/api/tasks/{created_task_id}/rerun")
    assert r.status_code == 201
    body = r.json()
    assert body["task_id"] != created_task_id
    assert body["status"] == "PLANNING"

    detail = await client.get(f"/api/tasks/{body['task_id']}")
    assert detail.status_code == 200
    original = await client.get(f"/api/tasks/{created_task_id}")
    assert detail.json()["goal"] == original.json()["goal"]
