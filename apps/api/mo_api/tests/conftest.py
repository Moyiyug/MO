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
from mo_api.workflows.execute_graph import build_execute_graph, reset_execute_graph_cache, set_execute_graph


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


@pytest.fixture
def execute_graph(tmp_path, monkeypatch):
    """隔离的 ExecuteMode LangGraph（MemorySaver，支持 ainvoke + async 节点）。"""
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_execute_graph(MemorySaver())
    set_execute_graph(graph)

    async def _ensure():
        return graph

    monkeypatch.setattr(
        "mo_api.workflows.execute_graph.ensure_execute_graph",
        _ensure,
    )
    monkeypatch.setattr(
        "mo_api.services.execution_service.ensure_execute_graph",
        _ensure,
    )
    try:
        yield graph
    finally:
        reset_execute_graph_cache()


@pytest.fixture(autouse=True)
def execute_graph_patch(execute_graph):
    """所有测试使用隔离 ExecuteGraph。"""
    yield execute_graph


@pytest.fixture(autouse=True)
def mock_execute_dependencies(monkeypatch, request, tmp_path):
    """Mock 仓库摄取与模型调用，避免真实联网/扣费。"""
    module = request.node.module.__name__
    if module.endswith("test_repo_ingest_adapter") or module.endswith(
        "test_model_gateway"
    ):
        yield
        return

    from mo_api.models.repo import RepoDigest

    class _FakeProfile:
        id = "fake"

    class _FakeGateway:
        def select(self, **kwargs):
            return _FakeProfile()

        async def complete(self, profile, messages, **kwargs):
            content = messages[0]["content"]
            if "core_modules" in content:
                return '{"core_modules":["main.py"], "execution_path":"main -> run"}'
            if "执行摘要" in content or "execution summary" in content.lower():
                return "已完成 repo_ingest 与 code_understanding 节点执行。"
            if "技术路线" in content or "technical route" in content.lower():
                return "技术路线从 main.py 入口经核心模块执行。"
            return '{"project_type":"library","entrypoints":["main.py"],"risks":[]}'

    async def fake_ingest(self, repo_url: str, *, token: str | None = None):
        return RepoDigest(
            summary="summary",
            tree="README.md",
            content={
                "README.md": "# demo",
                "requirements.txt": "requests>=2.0",
                "LICENSE": "MIT",
            },
            source_uri=repo_url,
        )

    chroma_dir = str(tmp_path / "chroma")
    settings_stub = type(
        "S",
        (),
        {
            "chroma_index_dir": chroma_dir,
            "repo_ingest_max_bytes": 50_000_000,
            "repo_ingest_exclude_patterns": ".git,.env",
        },
    )()

    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.GitingestAdapter.ingest",
        fake_ingest,
    )
    monkeypatch.setattr(
        "mo_api.services.execution_service.get_model_gateway",
        lambda: _FakeGateway(),
    )
    monkeypatch.setattr(
        "mo_api.services.report_service.get_model_gateway",
        lambda: _FakeGateway(),
    )
    monkeypatch.setattr(
        "mo_api.storage.vector_store.get_settings",
        lambda: settings_stub,
    )
    monkeypatch.setattr(
        "mo_api.services.execution_service.get_settings",
        lambda: settings_stub,
    )
    yield


@pytest.fixture(autouse=True)
def patch_get_engine(engine, monkeypatch):
    from mo_api.services.event_bus import reset_event_bus_cache
    from mo_api.services.execution_service import reset_execution_service_cache

    monkeypatch.setattr("mo_api.storage.db.get_engine", lambda: engine)
    monkeypatch.setattr("mo_api.services.event_bus.get_engine", lambda: engine)
    monkeypatch.setattr("mo_api.services.execution_service.get_engine", lambda: engine)
    reset_event_bus_cache()
    reset_execution_service_cache()
    reset_execute_graph_cache()
    yield
    reset_event_bus_cache()
    reset_execution_service_cache()
    reset_execute_graph_cache()


@pytest_asyncio.fixture
async def client(engine, plan_graph, execute_graph):
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
