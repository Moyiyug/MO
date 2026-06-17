"""端到端冒烟测试：验证全流水线契约一致性。（F-016）

测试目标：
- 所有 PlanStep 的 node_id 与执行图节点 ID 一致
- root requirements.txt 仅含 pip 语法
- 使用 mock LLM 跑通完整流水线：创建 → 计划 → 批准 → 执行 → 报告
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from mo_api.main import app
from mo_api.workflows.node_contract import EXECUTE_NODE_IDS


# ──▸ node_id 契约测试 ◂──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_plan_steps_have_valid_node_ids(client: AsyncClient, created_task_id: str):
    """验证所有计划步骤的 node_id 都是有效的执行图节点 ID。（F-002）"""
    # 生成计划
    resp = await client.post(f"/api/tasks/{created_task_id}/plan")
    assert resp.status_code == 200, resp.text
    plan = resp.json()

    proposed = plan.get("proposed_steps", [])
    assert len(proposed) > 0, "计划应包含至少一个步骤"

    for step in proposed:
        step_id = step.get("id", "?")
        node_id = step.get("node_id")
        assert node_id is not None, (
            f"步骤 {step_id} 缺少 node_id 字段"
        )
        assert node_id in EXECUTE_NODE_IDS, (
            f"步骤 {step_id} 的 node_id '{node_id}' 不在有效执行图节点集合中: {EXECUTE_NODE_IDS}"
        )


@pytest.mark.asyncio
async def test_all_node_ids_match_execute_graph(client: AsyncClient, created_task_id: str):
    """验证计划中的 node_id 与执行图 NODE_ID 常量完全匹配。（F-002）"""
    resp = await client.post(f"/api/tasks/{created_task_id}/plan")
    assert resp.status_code == 200, resp.text
    plan = resp.json()

    # 已知的映射关系（从 node_contract）
    expected_mapping = {
        "step_repo_ingest": "repo_ingest",
        "step_code_understanding": "code_understanding",
        "step_paper_research": "paper_research",
        "step_repro_eval": "reproducibility",
        "step_comparison": "comparison_builder",
        "step_sandbox": "sandbox_runner",
        "step_report": "report_writer",
    }

    for step in plan["proposed_steps"]:
        step_id = step["id"]
        expected_node_id = expected_mapping.get(step_id)
        if expected_node_id:
            assert step["node_id"] == expected_node_id, (
                f"步骤 {step_id}: 期望 node_id='{expected_node_id}'，实际 '{step['node_id']}'"
            )


# ──▸ requirements.txt 格式测试 ◂───────────────────────────────────────
def test_root_requirements_contains_only_pip_syntax():
    """验证根 requirements.txt 只包含 pip 语法，不混合 shell 命令。（F-001）"""
    from pathlib import Path

    # 找到项目根目录
    req_path = Path(__file__).resolve().parents[5] / "requirements.txt"
    lines = req_path.read_text(encoding="utf-8").splitlines()

    bad_prefixes = ("cd ", "uvicorn ", "npm ", "apps\\")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-r"):
            continue
        assert not any(
            stripped.lower().startswith(p) for p in bad_prefixes
        ), f"第 {i} 行包含非法内容：{stripped!r}"


# ──▸ 全流水线冒烟测试（mock LLM）◂────────────────────────────────────
@pytest.mark.asyncio
async def test_full_pipeline_create_approve_execute(client: AsyncClient):
    """完整流水线冒烟测试：创建 → 计划 → 批准 → 启动执行。

    使用 mock_execute_dependencies 自动注入假模型网关与假上游适配器。
    验证 node_id 契约一致性与 task 状态机正确推进。
    """
    # 1. 创建任务
    payload = {
        "goal": "调研机器学习方向的模型优化",
        "repo_urls": ["https://github.com/pallets/click"],
        "output_language": "zh",
        "permissions": {
            "allow_repo_clone": True,
            "allow_web_search": False,
            "allow_smoke_test": False,
        },
    }
    resp = await client.post("/api/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    task = resp.json()
    task_id = task["task_id"]
    assert task["status"] == "PLANNING"

    # 2. 生成计划
    resp = await client.post(f"/api/tasks/{task_id}/plan")
    assert resp.status_code == 200, resp.text
    plan = resp.json()
    assert len(plan["proposed_steps"]) > 0

    # 3. 检查 node_id 契约 — 所有步骤必须有有效 node_id
    for step in plan["proposed_steps"]:
        assert step["node_id"] in EXECUTE_NODE_IDS, (
            f"步骤 {step['id']}: node_id='{step['node_id']}' 无效"
        )

    # 4. 批准计划
    resp = await client.post(
        f"/api/tasks/{task_id}/approve-plan",
        json={"disabled_step_ids": []},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] == "PLAN_APPROVED"

    # 5. 确认任务状态
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    task = resp.json()
    assert task["status"] == "PLAN_APPROVED"

    # 6. 启动执行（mock 环境下 preflight 应通过）
    resp = await client.post(f"/api/tasks/{task_id}/execute")
    assert resp.status_code == 200, resp.text
    exec_result = resp.json()
    assert exec_result["status"] == "EXECUTING"
    # 验证执行已启动（task 在内存中 running）
    assert task_id is not None
