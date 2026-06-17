"""Preflight 失败路径集成测试（F-005）。

验证 POST /api/tasks/{task_id}/execute 在 preflight 检查失败时
正确返回 HTTP 409，且 detail 包含 "preflight_failed" code 与对应的错误信息。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_execute_fails_when_preflight_model_missing(client, monkeypatch):
    """Preflight 模型检查失败 → 409 preflight_failed。"""
    # 1. 创建任务
    resp = await client.post("/api/tasks", json={
        "goal": "test preflight model failure",
        "repo_urls": ["https://github.com/pallets/click"],
        "output_language": "zh",
        "permissions": {"allow_repo_clone": True},
    })
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    # 2. 生成计划
    resp = await client.post(f"/api/tasks/{task_id}/plan")
    assert resp.status_code == 200, resp.text

    # 3. 批准计划（推进到 PLAN_APPROVED）
    resp = await client.post(
        f"/api/tasks/{task_id}/approve-plan",
        json={"disabled_step_ids": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PLAN_APPROVED"

    # 4. Patch: 模型检查失败，git 检查正常
    monkeypatch.setattr(
        "mo_api.services.preflight_service.PreflightService.check_required_model_profiles",
        lambda self: ["缺少能力配置文件: mocked"],
    )

    async def _git_ok(self):
        return None

    monkeypatch.setattr(
        "mo_api.services.preflight_service.PreflightService.check_git_available",
        _git_ok,
    )

    # 5. 执行 → 409 with preflight_failed
    resp = await client.post(f"/api/tasks/{task_id}/execute")
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "preflight_failed"
    assert len(detail["errors"]) == 1
    assert "缺少能力配置文件" in detail["errors"][0]


@pytest.mark.asyncio
async def test_execute_fails_when_git_missing(client, monkeypatch):
    """Preflight git 检查失败 → 409 preflight_failed 含 git 相关错误信息。"""
    # 1. 创建任务
    resp = await client.post("/api/tasks", json={
        "goal": "test preflight git failure",
        "repo_urls": ["https://github.com/pallets/click"],
        "output_language": "zh",
        "permissions": {"allow_repo_clone": True},
    })
    assert resp.status_code == 201
    task_id = resp.json()["task_id"]

    # 2. 生成计划
    resp = await client.post(f"/api/tasks/{task_id}/plan")
    assert resp.status_code == 200, resp.text

    # 3. 批准计划
    resp = await client.post(
        f"/api/tasks/{task_id}/approve-plan",
        json={"disabled_step_ids": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PLAN_APPROVED"

    # 4. Patch: git 检查失败
    async def _git_error(self):
        return "未找到 git。请安装 Git（https://git-scm.com/）并确保其在 PATH 中。"

    monkeypatch.setattr(
        "mo_api.services.preflight_service.PreflightService.check_git_available",
        _git_error,
    )

    # 5. 执行 → 409 with preflight_failed 含 git 错误
    resp = await client.post(f"/api/tasks/{task_id}/execute")
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "preflight_failed"
    assert len(detail["errors"]) == 1
    assert "未找到 git" in detail["errors"][0]
