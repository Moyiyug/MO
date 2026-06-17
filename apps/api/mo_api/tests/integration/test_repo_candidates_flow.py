"""RepoDiscovery 候选选择流程集成测试（F-015）。

发现适配器在 conftest 中已 mock 为返回空，因此候选来自用户种子或显式选择，
不触发真实联网。
"""

from __future__ import annotations

import pytest

from mo_api.adapters.repo_discovery.base import RepoDiscoveryAdapter
from mo_api.models.repo_discovery import RepoCandidate


async def _create(client, goal: str, repo_urls: list[str]) -> str:
    resp = await client.post(
        "/api/tasks",
        json={"goal": goal, "repo_urls": repo_urls, "permissions": {"allow_repo_clone": True}},
    )
    assert resp.status_code == 201
    return resp.json()["task_id"]


async def test_seed_listed_as_candidate(client) -> None:
    task_id = await _create(client, "调研一个 RAG 框架", ["https://github.com/owner/seed"])
    await client.post(f"/api/tasks/{task_id}/plan")

    resp = await client.get(f"/api/tasks/{task_id}/repo-candidates")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == task_id
    assert len(body["candidates"]) == 1
    cand = body["candidates"][0]
    assert cand["repo_url"] == "https://github.com/owner/seed"
    assert cand["selected"] is True
    assert cand["discovered_by"] == "user_seed"


async def test_empty_repos_blocks_approval(client) -> None:
    task_id = await _create(client, "自动发现相关仓库", [])
    await client.post(f"/api/tasks/{task_id}/plan")

    task = await client.get(f"/api/tasks/{task_id}")
    assert task.json()["status"] == "WAITING_USER_APPROVAL"

    approve = await client.post(f"/api/tasks/{task_id}/approve-plan", json={})
    assert approve.status_code == 409


async def test_select_then_approve(client) -> None:
    task_id = await _create(client, "自动发现相关仓库", [])
    await client.post(f"/api/tasks/{task_id}/plan")

    select = await client.post(
        f"/api/tasks/{task_id}/repo-candidates",
        json={"selected_repo_urls": ["https://github.com/owner/chosen"]},
    )
    assert select.status_code == 200
    assert select.json()["candidates"][0]["selected"] is True

    task = await client.get(f"/api/tasks/{task_id}")
    assert task.json()["repo_urls"] == ["https://github.com/owner/chosen"]

    approve = await client.post(f"/api/tasks/{task_id}/approve-plan", json={})
    assert approve.status_code == 200
    assert approve.json()["status"] == "PLAN_APPROVED"


async def test_select_updates_flags_on_seeds(client) -> None:
    task_id = await _create(
        client,
        "对比两个框架",
        ["https://github.com/owner/a", "https://github.com/owner/b"],
    )
    await client.post(f"/api/tasks/{task_id}/plan")

    # 两个种子 -> 触发对比重点澄清，先回答以进入待审批
    await client.post(
        f"/api/tasks/{task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "可复现性"}]},
    )

    select = await client.post(
        f"/api/tasks/{task_id}/repo-candidates",
        json={"selected_repo_urls": ["https://github.com/owner/a"]},
    )
    assert select.status_code == 200
    cands = {c["repo_url"]: c for c in select.json()["candidates"]}
    assert cands["https://github.com/owner/a"]["selected"] is True
    assert cands["https://github.com/owner/b"]["selected"] is False

    task = await client.get(f"/api/tasks/{task_id}")
    assert task.json()["repo_urls"] == ["https://github.com/owner/a"]


async def test_select_invalid_url_rejected(client) -> None:
    task_id = await _create(client, "自动发现", [])
    await client.post(f"/api/tasks/{task_id}/plan")

    resp = await client.post(
        f"/api/tasks/{task_id}/repo-candidates",
        json={"selected_repo_urls": ["not-a-github-url"]},
    )
    assert resp.status_code == 409


async def test_select_too_many_rejected(client) -> None:
    task_id = await _create(client, "自动发现", [])
    await client.post(f"/api/tasks/{task_id}/plan")

    resp = await client.post(
        f"/api/tasks/{task_id}/repo-candidates",
        json={
            "selected_repo_urls": [
                f"https://github.com/o/r{i}" for i in range(6)
            ]
        },
    )
    assert resp.status_code == 422


async def test_full_discovery_flow_select_and_approve(client, monkeypatch) -> None:
    """完整"发现 + 选择"路径：GitHub 搜索返回候选 → 用户选择 → 批准成功。（F-015）"""
    # 构造返回 2 个模拟候选的 adapter
    fake_candidates = [
        RepoCandidate(
            repo_url="https://github.com/langchain-ai/langchain",
            repo_name="langchain-ai/langchain",
            description="Build context-aware reasoning applications",
            stars=95000,
            language="Python",
            topics=["llm", "agents"],
            relevance_score=0.0,
            discovered_by="github_search",
        ),
        RepoCandidate(
            repo_url="https://github.com/run-llama/llama_index",
            repo_name="run-llama/llama_index",
            description="Data framework for LLM applications",
            stars=37000,
            language="Python",
            topics=["rag", "agents"],
            relevance_score=0.0,
            discovered_by="github_search",
        ),
    ]

    class _NonEmptyAdapter(RepoDiscoveryAdapter):
        async def search(self, queries, *, per_query=5, limit=15):
            return list(fake_candidates)

    monkeypatch.setattr(
        "mo_api.workflows.nodes.repo_discovery.get_repo_discovery_adapter",
        lambda: _NonEmptyAdapter(),
    )

    # 1. 创建任务（空 repo_urls）
    task_id = await _create(client, "对比 LLM 应用框架", [])

    # 2. 生成计划 → repo_discovery 节点用 mock adapter 返回 2 个候选
    resp = await client.post(f"/api/tasks/{task_id}/plan")
    assert resp.status_code == 200, resp.text

    # 3. 回答澄清问题（空即可）
    await client.post(
        f"/api/tasks/{task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "生态与文档"}]},
    )

    # 4. GET repo-candidates → 应有 2 个候选
    resp = await client.get(f"/api/tasks/{task_id}/repo-candidates")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task_id"] == task_id
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["repo_name"] == "langchain-ai/langchain"
    assert body["candidates"][1]["repo_name"] == "run-llama/llama_index"
    # 初始状态：selected=False
    assert body["candidates"][0]["selected"] is False

    # 5. POST 选择第一个候选
    resp = await client.post(
        f"/api/tasks/{task_id}/repo-candidates",
        json={"selected_repo_urls": ["https://github.com/langchain-ai/langchain"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidates"][0]["selected"] is True
    assert body["candidates"][1]["selected"] is False

    # 6. 验证 task.repo_urls 已更新
    resp = await client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    task = resp.json()
    assert task["repo_urls"] == ["https://github.com/langchain-ai/langchain"]

    # 7. 批准计划 → 成功
    resp = await client.post(
        f"/api/tasks/{task_id}/approve-plan",
        json={"disabled_step_ids": []},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PLAN_APPROVED"
