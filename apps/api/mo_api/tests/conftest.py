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
    ) or module.endswith("test_paperqa_adapter") or module.endswith("test_paperqa_real"):
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
            if "MO 报告章节编辑器" in content:
                return (
                    '{"summary":"摘要","reader_markdown":"润色后的正文","warnings":[]}'
                )
            if "MO 最终报告编辑器" in content:
                return (
                    "# MO 深度调研报告\n\n"
                    "## 结论先行\n\n"
                    "基于对候选仓库的深入分析、资料调研和对比矩阵的评估，本次研究的核心判断是："
                    "候选方案在技术路线、工程成熟度和适用场景上各有侧重，暂无可无脑推荐的单一最优方案。"
                    "用户需结合具体场景需求和资源条件做出最终选型判断，本报告仅提供基于当前证据的综合分析。\n\n"
                    "## 为什么是这个判断\n\n"
                    "此判断基于以下几个方面的证据和分析：首先，仓库分析与代码结构解读揭示了各方案的核心抽象和架构模式；"
                    "其次，PaperQA 资料调研提供了学术界和工程界对这些框架的定位与评价；"
                    "最后，多维度对比矩阵对复现性、文档完整度、研究价值、工程契合度和可扩展性进行了系统评估。"
                    "虽然静态评估提供了较为全面的分析基础，但由于缺少实际运行日志，复现相关的结论仅属于静态推断，"
                    "不应被理解为实测验证结果。\n\n"
                    "## 候选方案如何理解\n\n"
                    "各候选方案在核心抽象、技术栈选择和目标场景方面存在明显差异。"
                    "通过仓库档案分析，每个方案都有其独特的设计哲学和适用边界，"
                    "不存在放之四海皆准的统一方案。用户需要结合自身的技术栈偏好、团队经验和项目需求来理解这些差异。\n\n"
                    "## 关键权衡\n\n"
                    "在选择方案时需要重点关注以下权衡：工程成熟度与前沿创新的平衡、"
                    "文档完整度与社区活跃度的关系、复现难易度与技术复杂度的矛盾、"
                    "以及特定场景优化与通用性的取舍。没有完美的方案，只有更适合当前需求的方案。\n\n"
                    "## 不确定性与边界\n\n"
                    "本次研究存在以下不确定性和边界：复现评估均为静态分析，未经实际运行验证；"
                    "部分证据为弱证据或模型推断，需要人工审核确认；"
                    "对比矩阵的权重设置可能影响最终排名，建议用户根据自身场景调整权重后重新评估；"
                    "调研无法覆盖所有边缘场景和最新版本变化，结论具有时效性限制。\n\n"
                    "## 下一步验证路线\n\n"
                    "建议的后续验证步骤包括：对排名靠前的仓库进行实际安装和冒烟测试验证；"
                    "补充弱证据相关的文档和代码验证；结合具体业务场景进行概念验证开发；"
                    "持续关注相关仓库的版本更新和社区动态。\n"
                )
            if "研究综合" in content or "research synthesis" in content.lower():
                return (
                    '{"thesis":"初步判断目标仓库方案各有侧重。",'
                    '"key_insights":["洞察1"],'
                    '"repo_interpretations":{"owner/repo-a":"已采集证据"},'
                    '"tradeoffs":["权衡1"],'
                    '"uncertainty":["不确定性1"],'
                    '"next_questions":["下一步1"],'
                    '"evidence_ids":[]}'
                )
            if "执行摘要" in content or "execution summary" in content.lower():
                return "已完成 repo_ingest 与 code_understanding 节点执行。"
            if "技术路线" in content or "technical route" in content.lower():
                return "技术路线从 main.py 入口经核心模块执行。"
            if "Score repo on dimension" in content:
                return '{"score": 0.75, "rationale": "demo comparison score"}'
            if "Classify this research material" in content:
                return (
                    '{"material_type": "official_repo_paper", '
                    '"relationship_clear": true}'
                )
            if "Score reproducibility dimension" in content:
                return (
                    '{"score": 0.72, "reason": "demo repro score", '
                    '"missing_info": []}'
                )
            return '{"project_type":"library","entrypoints":["main.py"],"risks":[]}'

    class _FakeProfileStore:
        def has_api_key(self, profile) -> bool:
            return True

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
            "paper_index_dir": str(tmp_path / "paper_idx"),
            "web_search_retriever": "",
        },
    )()

    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.adapters.paper_research.base import (
        PaperAnswer,
        PaperContext,
        WebResearchResult,
        WebSource,
    )

    async def fake_query_papers(self, doc_paths, question, *, task_id):
        return PaperAnswer(
            answer="demo paper answer",
            contexts=[
                PaperContext(
                    text="demo paper context",
                    source_name="paper.pdf",
                    locator="p1",
                )
            ],
        )

    async def fake_web_research(self, query, *, report_type="research_report"):
        return WebResearchResult(
            report="demo web report",
            sources=[
                WebSource(url="https://example.com/ref", summary="background ref")
            ],
        )

    # RepoDiscovery（F-015）：PlanMode 节点不得真实访问 GitHub / 调模型
    from mo_api.adapters.repo_discovery.base import RepoDiscoveryAdapter

    class _FakeDiscoveryAdapter(RepoDiscoveryAdapter):
        async def search(self, queries, *, per_query=5, limit=15):
            return []

    monkeypatch.setattr(
        "mo_api.workflows.nodes.repo_discovery.get_repo_discovery_adapter",
        lambda: _FakeDiscoveryAdapter(),
    )
    monkeypatch.setattr(
        "mo_api.workflows.nodes.repo_discovery.get_model_gateway",
        lambda: _FakeGateway(),
    )

    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.GitingestAdapter.ingest",
        fake_ingest,
    )
    monkeypatch.setattr(PaperQAAdapter, "query_papers", fake_query_papers)
    monkeypatch.setattr(GPTResearcherAdapter, "research", fake_web_research)
    monkeypatch.setattr(
        "mo_api.services.execution_service.get_model_gateway",
        lambda: _FakeGateway(),
    )
    monkeypatch.setattr(
        "mo_api.services.report_service.get_model_gateway",
        lambda: _FakeGateway(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.get_model_gateway",
        lambda: _FakeGateway(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.profiles.get_profile_store",
        lambda: _FakeProfileStore(),
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
