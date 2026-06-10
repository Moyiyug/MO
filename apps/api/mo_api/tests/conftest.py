"""共享测试 fixture。

为每个测试构造隔离的临时 SQLite，并覆盖 get_session 依赖，
避免污染 runtime/ 真实数据库；提供 httpx 异步 client。
"""

from __future__ import annotations

import sqlite3

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.sqlite import SqliteSaver
from sqlmodel import Session, SQLModel, create_engine

from mo_api.main import app
from mo_api.storage import tables as _tables  # noqa: F401  确保表注册
from mo_api.storage.db import get_session
from mo_api.workflows.graph import build_plan_graph


@pytest.fixture
def engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def plan_graph(tmp_path, monkeypatch):
    """隔离的 LangGraph checkpointer（临时 SQLite）。"""
    db_path = tmp_path / "checkpoints.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    graph = build_plan_graph(saver)
    monkeypatch.setattr("mo_api.workflows.graph.get_plan_graph", lambda: graph)
    monkeypatch.setattr("mo_api.routers.plans.get_plan_graph", lambda: graph)
    try:
        yield graph
    finally:
        conn.close()


@pytest_asyncio.fixture
async def client(engine, plan_graph):
    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def created_task_id(client, valid_task_payload):
    resp = await client.post("/api/tasks", json=valid_task_payload)
    assert resp.status_code == 201
    return resp.json()["task_id"]


@pytest.fixture
def valid_task_payload() -> dict:
    return {
        "goal": "对比两个 RAG 框架的可复现性",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
