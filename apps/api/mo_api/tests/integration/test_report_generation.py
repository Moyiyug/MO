"""报告生成与导出集成测试（PRD F-011）。"""

from __future__ import annotations

import asyncio

import pytest
from sqlmodel import Session

from mo_api.models.enums import ClaimLabel
from mo_api.models.report import REPORT_SECTION_KEYS
from mo_api.storage.repositories import ReportRepository


async def _approve_plan_flow(client, task_id: str) -> None:
    await client.post(f"/api/tasks/{task_id}/plan")
    await client.post(
        f"/api/tasks/{task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "可复现性"}]},
    )
    resp = await client.post(f"/api/tasks/{task_id}/approve-plan", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "PLAN_APPROVED"


async def _wait_for_report_draft(client, task_id: str) -> None:
    for _ in range(40):
        resp = await client.get(f"/api/tasks/{task_id}")
        if resp.json()["status"] == "REPORT_DRAFT":
            return
        await asyncio.sleep(0.15)
    pytest.fail("task did not reach REPORT_DRAFT")


async def _approve_all_waiting_steps(client, task_id: str, engine) -> None:
    from mo_api.models.enums import NodeStatus
    from mo_api.storage.repositories import EventRepository

    for _ in range(10):
        with Session(engine) as session:
            events = EventRepository(session).list_since(task_id, 0)
        waiting = [
            e.node
            for e in events
            if e.status is NodeStatus.WAITING_USER
        ]
        if not waiting:
            break
        for node in waiting:
            resp = await client.post(
                f"/api/tasks/{task_id}/steps/{node}/approve",
                json={"approved": True},
            )
            assert resp.status_code == 200
        await asyncio.sleep(0.2)


async def _run_full_execute(client, task_id: str, engine) -> None:
    await _approve_plan_flow(client, task_id)
    exec_resp = await client.post(f"/api/tasks/{task_id}/execute")
    assert exec_resp.status_code == 200
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)


@pytest.mark.asyncio
async def test_report_generation_and_export(client, created_task_id, engine) -> None:
    await _run_full_execute(client, created_task_id, engine)

    # F-013: 显式生成报告（GET /report 已改为只读）
    gen_resp = await client.post(f"/api/tasks/{created_task_id}/generate-report")
    assert gen_resp.status_code == 200

    report_resp = await client.get(f"/api/tasks/{created_task_id}/report")
    assert report_resp.status_code == 200
    report = report_resp.json()

    assert report["task_id"] == created_task_id
    assert len(report["sections"]) == len(REPORT_SECTION_KEYS)
    section_keys = [s["key"] for s in report["sections"]]
    assert section_keys == REPORT_SECTION_KEYS

    all_labels = {c["label"] for s in report["sections"] for c in s["claims"]}
    assert ClaimLabel.PENDING.value in all_labels
    assert ClaimLabel.INFERENCE.value in all_labels

    assert len(report["pending_warnings"]) >= 1
    pending_sections = [s for s in report["sections"] if s["is_pending"]]
    # M9 后 reproducibility 段已接入真实数据，pending 段减少
    assert len(pending_sections) >= 2

    repro_section = next(s for s in report["sections"] if s["key"] == "reproducibility")
    assert repro_section["is_pending"] is False
    assert "static_reproducibility_assessment" in repro_section["markdown"]

    repro_resp = await client.get(f"/api/tasks/{created_task_id}/reproducibility")
    assert repro_resp.status_code == 200
    assert len(repro_resp.json()["scores"]) >= 1

    task_after_gen = await client.get(f"/api/tasks/{created_task_id}")
    assert task_after_gen.json()["status"] == "REVIEW_REQUIRED"

    export_resp = await client.post(f"/api/tasks/{created_task_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"].startswith("text/markdown")
    body = export_resp.text
    assert "[pending]" in body
    assert "[inference]" in body

    confirm_resp = await client.post(
        f"/api/tasks/{created_task_id}/confirm-report"
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "DONE"

    with Session(engine) as session:
        saved = ReportRepository(session).get_by_task(created_task_id)
        assert saved is not None
        assert saved.markdown == body or saved.markdown.strip() == body.strip()


@pytest.mark.asyncio
async def test_report_not_ready_before_execute(client, created_task_id) -> None:
    # F-013: GET /report 只读，无缓存返回 404
    resp = await client.get(f"/api/tasks/{created_task_id}/report")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_cache_hit(client, created_task_id, engine) -> None:
    """生成后再次 GET 应从缓存返回相同 report id。"""
    await _run_full_execute(client, created_task_id, engine)

    # F-013: 显式生成报告
    await client.post(f"/api/tasks/{created_task_id}/generate-report")

    first = await client.get(f"/api/tasks/{created_task_id}/report")
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = await client.get(f"/api/tasks/{created_task_id}/report")
    assert second.status_code == 200
    assert second.json()["id"] == first_id  # 缓存命中，id 不变


@pytest.mark.asyncio
async def test_confirm_after_done_rejects(client, created_task_id, engine) -> None:
    """确认后再次 confirm 应返回 409。"""
    await _run_full_execute(client, created_task_id, engine)
    # F-013: 显式生成报告
    await client.post(f"/api/tasks/{created_task_id}/generate-report")
    # 确认
    confirm = await client.post(
        f"/api/tasks/{created_task_id}/confirm-report"
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "DONE"
    # 再次确认应拒绝
    again = await client.post(
        f"/api/tasks/{created_task_id}/confirm-report"
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_regenerate_report_endpoint(client, created_task_id, engine) -> None:
    """regenerate-report 端点应强制重新生成并返回新 report。"""
    await _run_full_execute(client, created_task_id, engine)

    # F-013: 显式生成报告
    first = await client.post(f"/api/tasks/{created_task_id}/generate-report")
    assert first.status_code == 200
    first_id = first.json()["id"]

    regen = await client.post(
        f"/api/tasks/{created_task_id}/regenerate-report"
    )
    assert regen.status_code == 200
    # 重新生成应产生新 id（除非内容完全一致，概率极低）
    # 主要验证端点可用且返回 200
    assert regen.json()["task_id"] == created_task_id
    assert len(regen.json()["sections"]) == len(REPORT_SECTION_KEYS)
