"""任务 API 集成测试（PRD F-001, §5, F-015）。"""

from __future__ import annotations


async def test_create_task_returns_planning(client, valid_task_payload) -> None:
    resp = await client.post("/api/tasks", json=valid_task_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PLANNING"          # F-001
    assert body["task_id"]


async def test_create_then_get_detail(client, valid_task_payload) -> None:
    created = (await client.post("/api/tasks", json=valid_task_payload)).json()
    resp = await client.get(f"/api/tasks/{created['task_id']}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["task_id"] == created["task_id"]
    assert detail["goal"] == valid_task_payload["goal"]
    assert detail["status"] == "PLANNING"
    assert detail["repo_urls"] == valid_task_payload["repo_urls"]


async def test_list_tasks(client, valid_task_payload) -> None:
    await client.post("/api/tasks", json=valid_task_payload)
    await client.post("/api/tasks", json=valid_task_payload)
    resp = await client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_missing_task_404(client) -> None:
    resp = await client.get("/api/tasks/does-not-exist")
    assert resp.status_code == 404


async def test_create_rejects_invalid_repo_url(client) -> None:
    resp = await client.post(
        "/api/tasks",
        json={"goal": "x", "repo_urls": ["not-a-github-url"]},
    )
    assert resp.status_code == 422


async def test_create_rejects_too_many_repos(client) -> None:
    resp = await client.post(
        "/api/tasks",
        json={
            "goal": "x",
            "repo_urls": [f"https://github.com/o/r{i}" for i in range(6)],
        },
    )
    assert resp.status_code == 422


async def test_create_accepts_empty_repos(client) -> None:
    """F-015：repo_urls 可留空，由 RepoDiscovery 自动发现。"""
    resp = await client.post(
        "/api/tasks",
        json={"goal": "对比 RAG 框架", "repo_urls": []},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "PLANNING"


async def test_create_accepts_missing_repos(client, valid_task_payload) -> None:
    """F-015：未提供 repo_urls 字段时也应被接受（默认空列表）。"""
    payload = dict(valid_task_payload)
    payload.pop("repo_urls")
    resp = await client.post("/api/tasks", json=payload)
    assert resp.status_code == 201


async def test_create_rejects_missing_goal(client, valid_task_payload) -> None:
    payload = dict(valid_task_payload)
    payload.pop("goal")
    resp = await client.post("/api/tasks", json=payload)
    assert resp.status_code == 422
