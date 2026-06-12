"""RepoDiscovery 候选选择流程集成测试（F-015）。

发现适配器在 conftest 中已 mock 为返回空，因此候选来自用户种子或显式选择，
不触发真实联网。
"""

from __future__ import annotations


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
