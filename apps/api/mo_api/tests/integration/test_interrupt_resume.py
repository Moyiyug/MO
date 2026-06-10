"""LangGraph interrupt / resume 集成测试。"""

from __future__ import annotations

import pytest
from langgraph.types import Command


async def test_graph_interrupts_before_approval(plan_graph, created_task_id, client) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    config = {"configurable": {"thread_id": f"{created_task_id}:v1"}}
    snapshot = plan_graph.get_state(config)
    assert snapshot.next == ("approval_gate",)
    assert snapshot.values.get("plan")


async def test_resume_after_approve_completes_graph(
    plan_graph, created_task_id, client
) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    await client.post(
        f"/api/tasks/{created_task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "综合对比"}]},
    )
    config = {"configurable": {"thread_id": f"{created_task_id}:v2"}}
    assert plan_graph.get_state(config).next == ("approval_gate",)

    plan_graph.invoke(Command(resume={"approved": True}), config)
    assert plan_graph.get_state(config).next == ()


async def test_duplicate_approve_is_idempotent_conflict(client, created_task_id) -> None:
    await client.post(f"/api/tasks/{created_task_id}/plan")
    await client.post(
        f"/api/tasks/{created_task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "研究价值"}]},
    )
    first = await client.post(
        f"/api/tasks/{created_task_id}/approve-plan",
        json={},
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/tasks/{created_task_id}/approve-plan",
        json={},
    )
    assert second.status_code == 409
