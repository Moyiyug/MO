"""ExecuteMode LangGraph 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import asyncio

import pytest
from langgraph.types import Command
from sqlmodel import Session

from mo_api.models.enums import TaskStatus
from mo_api.models.repo import RepoDigest
from mo_api.services.event_bus import EventBus
from mo_api.services.execution_service import ExecutionService
from mo_api.storage.repositories import EventRepository, TaskRepository
from mo_api.storage.tables import TaskTable
from mo_api.workflows.execute_graph import build_execute_graph


class _FakeProfile:
    id = "fake"


@pytest.fixture
def mock_repo_ingest(monkeypatch):
    async def fake_ingest(self, repo_url: str, *, token: str | None = None):
        return RepoDigest(
            summary="summary",
            tree="README.md",
            content={
                "README.md": "# demo",
                "requirements.txt": "requests>=2.0",
                "LICENSE": "MIT License",
            },
            source_uri=repo_url,
        )

    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.GitingestAdapter.ingest",
        fake_ingest,
    )


@pytest.fixture
def mock_gateway(monkeypatch):
    async def fake_complete(self, profile, messages, **kwargs):
        content = messages[0]["content"]
        if "core_modules" in content:
            return '{"core_modules":["main.py"], "execution_path":"main -> run"}'
        if "Score repo on dimension" in content:
            return '{"score": 0.75, "rationale": "demo comparison score"}'
        if "Classify this research material" in content:
            return '{"material_type": "background_reference", "relationship_clear": true}'
        if "Score reproducibility dimension" in content:
            return '{"score": 0.7, "reason": "demo", "missing_info": []}'
        return '{"project_type":"library","entrypoints":["main.py"],"risks":["low test coverage"]}'

    def fake_select(self, **kwargs):
        return _FakeProfile()

    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.ModelGateway.complete",
        fake_complete,
    )
    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.ModelGateway.select",
        fake_select,
    )


def _seed_task(engine, task_id: str, *, allow_clone: bool = True) -> None:
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="理解仓库结构",
                repo_urls=["https://github.com/o/r"],
                paper_urls=[],
                status=TaskStatus.PLAN_APPROVED.value,
                permissions={"allow_repo_clone": allow_clone},
            )
        )
        session.commit()


@pytest.mark.asyncio
async def test_execute_graph_interrupt_and_resume(
    engine,
    execute_graph,
    mock_repo_ingest,
    mock_gateway,
) -> None:
    task_id = "graph-interrupt"
    _seed_task(engine, task_id, allow_clone=False)
    bus = EventBus()
    executor = ExecutionService(bus)

    await executor.start(task_id)
    import asyncio

    for _ in range(50):
        if executor._pending_interrupt.get(task_id):
            break
        await asyncio.sleep(0.05)
    assert executor._pending_interrupt.get(task_id) == "repo_ingest"

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(
            e.node == "repo_ingest" and e.status.value == "waiting_user" for e in events
        )

    await executor.approve_step(task_id, "repo_ingest", True)

    task = None
    for _ in range(40):
        await asyncio.sleep(0.1)
        with Session(engine) as session:
            task = TaskRepository(session).get(task_id)
            if task is not None and task.status is TaskStatus.REPORT_DRAFT:
                break

    with Session(engine) as session:
        assert task is not None
        assert task.status is TaskStatus.REPORT_DRAFT
        events = EventRepository(session).list_since(task_id, 0)
        nodes = {e.node for e in events if e.status.value == "completed"}
        assert "repo_ingest" in nodes
        assert "code_understanding" in nodes


@pytest.mark.asyncio
async def test_resume_rejected_fails_task(
    engine,
    execute_graph,
    mock_repo_ingest,
    mock_gateway,
) -> None:
    import asyncio

    task_id = "graph-reject"
    _seed_task(engine, task_id, allow_clone=False)
    executor = ExecutionService(EventBus())

    await executor.start(task_id)
    for _ in range(50):
        if executor._pending_interrupt.get(task_id):
            break
        await asyncio.sleep(0.05)

    await executor.approve_step(task_id, "repo_ingest", False)
    await asyncio.sleep(0.2)

    with Session(engine) as session:
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_graph_direct_invoke(
    execute_graph,
    engine,
    tmp_path,
    mock_repo_ingest,
    mock_gateway,
) -> None:
    task_id = "direct-graph"
    config = {"configurable": {"thread_id": f"exec:{task_id}"}}
    state = {
        "task_id": task_id,
        "goal": "analyze repo",
        "repo_urls": ["https://github.com/o/r"],
        "permissions": {"allow_repo_clone": True},
        "repo_cards": [],
        "evidence_items": [],
        "ingested_repos": [],
        "code_insights": [],
        "paper_materials": [],
        "reproducibility": None,
        "comparison": None,
        "errors": [],
    }

    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.adapters.repo_ingest import GitingestAdapter
    from mo_api.services.evidence_service import EvidenceService
    from mo_api.services.event_bus import EventBus
    from mo_api.storage.vector_store import TaskVectorStore
    from mo_api.workflows.execute_context import (
        ExecuteContext,
        clear_context,
        register_context,
    )

    class _FakeProfile:
        id = "fake"

    class _FakeGateway:
        def select(self, **kwargs):
            return _FakeProfile()

        async def complete(self, profile, messages, **kwargs):
            content = messages[0]["content"]
            if "core_modules" in content:
                return '{"core_modules":["main.py"], "execution_path":"main -> run"}'
            if "Score repo on dimension" in content:
                return '{"score": 0.75, "rationale": "demo"}'
            if "Classify this research material" in content:
                return '{"material_type": "background_reference", "relationship_clear": true}'
            if "Score reproducibility dimension" in content:
                return '{"score": 0.7, "reason": "demo", "missing_info": []}'
            return '{"project_type":"library","entrypoints":["main.py"],"risks":[]}'

    chroma_dir = str(tmp_path / "chroma")
    with Session(engine) as session:
        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=_FakeGateway()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=_FakeGateway(),
                vector_store_factory=lambda tid: TaskVectorStore(
                    tid, persist_dir=chroma_dir
                ),
            ),
        )
        try:
            result = await execute_graph.ainvoke(state, config)
        finally:
            clear_context(task_id)

    assert result.get("repo_cards")
    assert result.get("code_insights")
