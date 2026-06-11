"""复现评估节点单元测试（PRD F-007）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import (
    REPRO_DIMENSIONS,
    STATIC_REPRO_ASSESSMENT_LABEL,
    TaskStatus,
)
from mo_api.models.repo import RepoCard
from mo_api.storage.repositories import ReproducibilityRepository, RepoCardRepository
from mo_api.storage.tables import TaskTable
from mo_api.workflows.nodes.reproducibility import reproducibility


class _FakeProfile:
    id = "fake"


class _FakeGateway:
    def select(self, **kwargs):
        return _FakeProfile()

    async def complete(self, profile, messages, **kwargs):
        content = messages[0]["content"]
        if "Score reproducibility dimension" in content:
            return '{"score": 0.8, "reason": "demo repro score", "missing_info": []}'
        return "{}"


def _seed_task_with_card(engine, task_id: str) -> None:
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="repro test",
                repo_urls=["https://github.com/o/r"],
                paper_urls=[],
                status=TaskStatus.EXECUTING.value,
                permissions={},
            )
        )
        RepoCardRepository(session).create(
            RepoCard(
                id=uuid.uuid4().hex,
                task_id=task_id,
                repo_url="https://github.com/o/r",
                repo_name="r",
                summary="demo repo",
                dependencies=["requests"],
                entrypoints=["main.py"],
                test_commands=["pytest"],
                docs_paths=["README.md"],
                license="MIT",
                risks=[],
            )
        )
        session.commit()


@pytest.mark.asyncio
async def test_reproducibility_eight_dimensions_and_label(
    engine, monkeypatch, tmp_path
) -> None:
    from mo_api.adapters.repo_ingest import GitingestAdapter
    from mo_api.services.evidence_service import EvidenceService
    from mo_api.services.event_bus import EventBus
    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.workflows.execute_context import (
        ExecuteContext,
        clear_context,
        register_context,
    )

    task_id = "repro-node-test"
    _seed_task_with_card(engine, task_id)

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
                vector_store_factory=lambda tid: type(
                    "VS", (), {"add_texts": lambda *a, **k: None}
                )(),
            ),
        )
        try:
            result = await reproducibility({"task_id": task_id})
        finally:
            clear_context(task_id)

    repro = result.get("reproducibility") or {}
    scores = repro.get("scores") or []
    assert len(scores) == 1
    score = scores[0]
    assert score["assessment_label"] == STATIC_REPRO_ASSESSMENT_LABEL
    assert set(score["dimension_scores"].keys()) == set(REPRO_DIMENSIONS)
    assert 0.0 <= score["overall_score"] <= 1.0
    assert len(score["evidence_ids"]) == len(REPRO_DIMENSIONS)

    with Session(engine) as session:
        stored = ReproducibilityRepository(session).get_by_task(task_id)
        assert stored is not None
        assert stored.scores[0].assessment_label == STATIC_REPRO_ASSESSMENT_LABEL


@pytest.mark.asyncio
async def test_paper_research_pending_when_relationship_unclear(
    engine, monkeypatch, tmp_path
) -> None:
    from mo_api.adapters.paper_research.base import PaperAnswer, PaperContext
    from mo_api.adapters.repo_ingest import GitingestAdapter
    from mo_api.services.evidence_service import EvidenceService
    from mo_api.services.event_bus import EventBus
    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.workflows.execute_context import (
        ExecuteContext,
        clear_context,
        register_context,
    )
    from mo_api.workflows.nodes.paper_research import paper_research

    class _UnclearGateway(_FakeGateway):
        async def complete(self, profile, messages, **kwargs):
            content = messages[0]["content"]
            if "Classify this research material" in content:
                return '{"material_type": "official_repo_paper", "relationship_clear": false}'
            return await super().complete(profile, messages, **kwargs)

    async def fake_query(self, doc_paths, question, *, task_id):
        return PaperAnswer(
            answer="a",
            contexts=[PaperContext(text="ctx", source_name="p.pdf", locator="p1")],
        )

    monkeypatch.setattr(PaperQAAdapter, "query_papers", fake_query)

    task_id = "paper-pending-test"
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="paper test",
                repo_urls=["https://github.com/o/r"],
                paper_urls=["https://arxiv.org/abs/1234"],
                status=TaskStatus.EXECUTING.value,
                permissions={"allow_web_search": False},
            )
        )
        session.commit()

        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=_UnclearGateway()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=_UnclearGateway(),
                vector_store_factory=lambda tid: type(
                    "VS", (), {"add_texts": lambda *a, **k: None}
                )(),
            ),
        )
        try:
            result = await paper_research(
                {
                    "task_id": task_id,
                    "goal": "paper test",
                    "paper_urls": ["https://arxiv.org/abs/1234"],
                    "repo_urls": ["https://github.com/o/r"],
                    "permissions": {"allow_web_search": False},
                }
            )
        finally:
            clear_context(task_id)

    materials = result.get("paper_materials") or []
    assert materials
    assert materials[0]["material_type"] == "unverified_reference"
    assert materials[0]["relationship_clear"] is False


@pytest.mark.asyncio
async def test_reproducibility_llm_failure_per_dimension(
    engine, monkeypatch, tmp_path
) -> None:
    """单维 LLM 失败不崩溃——失败维度 score=0，其余维度正常。"""
    from mo_api.adapters.repo_ingest import GitingestAdapter
    from mo_api.services.evidence_service import EvidenceService
    from mo_api.services.event_bus import EventBus
    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.workflows.execute_context import (
        ExecuteContext, clear_context, register_context,
    )

    task_id = "repro-fail-test"
    _seed_task_with_card(engine, task_id)

    class _SelectiveFailGateway(_FakeGateway):
        _count = 0

        async def complete(self, profile, messages, **kwargs):
            self._count += 1
            if self._count == 3:
                raise Exception("LLM timeout")
            return await super().complete(profile, messages, **kwargs)

    with Session(engine) as session:
        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=_SelectiveFailGateway()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=_SelectiveFailGateway(),
                vector_store_factory=lambda tid: type(
                    "VS", (), {"add_texts": lambda *a, **k: None}
                )(),
            ),
        )
        try:
            result = await reproducibility({"task_id": task_id})
        finally:
            clear_context(task_id)

    repro = result.get("reproducibility") or {}
    scores = repro.get("scores") or []
    assert len(scores) == 1
    dims = scores[0]["dimension_scores"]
    assert len(dims) == len(REPRO_DIMENSIONS)
    assert 0.0 in dims.values()


@pytest.mark.asyncio
async def test_reproducibility_empty_repos_skipped(
    engine, monkeypatch, tmp_path
) -> None:
    """空仓库列表时应发送 SKIPPED 事件。"""
    from mo_api.adapters.repo_ingest import GitingestAdapter
    from mo_api.services.evidence_service import EvidenceService
    from mo_api.services.event_bus import EventBus
    from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
    from mo_api.workflows.execute_context import (
        ExecuteContext, clear_context, register_context,
    )
    from mo_api.models.enums import NodeStatus
    from mo_api.storage.repositories import EventRepository

    task_id = "repro-empty-test"
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="empty test",
                repo_urls=[],
                paper_urls=[],
                status=TaskStatus.EXECUTING.value,
                permissions={},
            )
        )
        session.commit()

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
                vector_store_factory=lambda tid: type(
                    "VS", (), {"add_texts": lambda *a, **k: None}
                )(),
            ),
        )
        try:
            result = await reproducibility({"task_id": task_id})
        finally:
            clear_context(task_id)

    assert result.get("reproducibility") is None
    events = EventRepository(session).list_since(task_id, 0)
    assert any(e.status is NodeStatus.SKIPPED for e in events)
