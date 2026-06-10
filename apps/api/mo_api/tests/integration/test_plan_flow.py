"""PlanMode API 集成测试（PRD F-002 / F-003）。"""

from __future__ import annotations

import pytest


async def test_generate_plan_returns_structured_plan(client, created_task_id) -> None:
    resp = await client.post(f"/api/tasks/{created_task_id}/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == created_task_id
    assert body["confirmed_context"]
    assert body["proposed_steps"]
    assert body["report_rubric"]["weights"]
    assert body["risk_summary"]

    task = await client.get(f"/api/tasks/{created_task_id}")
    assert task.json()["status"] == "WAITING_USER_CLARIFICATION"


async def test_get_latest_plan(client, created_task_id) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    resp = await client.get(f"/api/tasks/{created_task_id}/plan")
    assert resp.status_code == 200
    assert resp.json()["task_id"] == created_task_id


async def test_clarifications_then_approval(client, created_task_id) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    clar = await client.post(
        f"/api/tasks/{created_task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "可复现性"}]},
    )
    assert clar.status_code == 200
    assert clar.json()["confirmed_context"][-1].startswith("对比重点")

    task = await client.get(f"/api/tasks/{created_task_id}")
    assert task.json()["status"] == "WAITING_USER_APPROVAL"

    approve = await client.post(
        f"/api/tasks/{created_task_id}/approve-plan",
        json={},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "PLAN_APPROVED"


async def test_invalid_clarification_question_keeps_waiting_for_clarification(
    client, created_task_id
) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")

    clar = await client.post(
        f"/api/tasks/{created_task_id}/clarifications",
        json={"answers": [{"question_id": "typo_focus", "answer": "可复现性"}]},
    )
    assert clar.status_code == 409
    assert "unknown clarification question_id" in clar.json()["detail"]

    task = await client.get(f"/api/tasks/{created_task_id}")
    assert task.json()["status"] == "WAITING_USER_CLARIFICATION"


async def test_approve_without_plan_returns_409(client, created_task_id) -> None:
    resp = await client.post(
        f"/api/tasks/{created_task_id}/approve-plan",
        json={},
    )
    assert resp.status_code == 409


async def test_replan_creates_new_plan(client, created_task_id) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    await client.post(
        f"/api/tasks/{created_task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "工程成熟度"}]},
    )
    await client.post(f"/api/tasks/{created_task_id}/approve-plan", json={})

    replan = await client.post(
        f"/api/tasks/{created_task_id}/replan",
        json={"reason": "证据冲突"},
    )
    assert replan.status_code == 200

    task = await client.get(f"/api/tasks/{created_task_id}")
    assert task.json()["status"] in {"WAITING_USER_CLARIFICATION", "WAITING_USER_APPROVAL"}
