"""paper_research 节点单元测试（PRD F1 / F2 / F3）。

覆盖：
- _build_deep_research_questions 返回 4 个深度问题
- _query_paperqa_answers 多问题查询、answer records、context evidence ids
- 单问题失败不阻塞其他问题
- paper_research 节点写 paperqa_answers 到 seed
- web_report 写入 seed structured_data
- narrative_seed 包含 PaperQA 回答摘要
- 所有问题均失败时的降级行为
- 无 doc_paths 时创建 pending evidence
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.adapters.paper_research.base import (
    PaperAnswer,
    PaperContext,
    PaperResearchError,
    WebResearchResult,
    WebSource,
)
from mo_api.models.enums import MaterialType, SourceType, TaskStatus
from mo_api.models.evidence import EvidenceItem
from mo_api.models.reproducibility import PaperMaterial
from mo_api.models.research_synthesis import PaperQAAnswerRecord
from mo_api.services.evidence_service import EvidenceService
from mo_api.storage.repositories import ReportSectionSeedRepository
from mo_api.storage.tables import TaskTable
from mo_api.workflows.nodes.paper_research import (
    _build_deep_research_questions,
    _query_paperqa_answers,
    paper_research,
)
from mo_api.workflows.execute_context import (
    ExecuteContext,
    register_context,
    clear_context,
)


def _seed_task(session: Session, task_id: str) -> None:
    session.add(
        TaskTable(
            id=task_id,
            goal="对比 RAG 框架的可复现性",
            repo_urls=["https://github.com/owner/repo-a"],
            paper_urls=[],
            output_language="zh",
            template=None,
            permissions={"allow_repo_clone": True, "allow_web_search": False},
            status=TaskStatus.REPORT_DRAFT.value,
        )
    )
    session.commit()


def _make_paper_adapter(
    answers: list[PaperAnswer | Exception] | None = None,
) -> MagicMock:
    """构造返回指定 answers 的 paper_adapter mock。"""
    adapter = MagicMock()
    if answers is None:
        adapter.query_papers = AsyncMock(
            return_value=PaperAnswer(
                answer="综合回答",
                contexts=[
                    PaperContext(
                        text="context text",
                        source_name="paper.pdf",
                        locator="p1",
                    )
                ],
            )
        )
    else:
        async def _side_effect(doc_paths, question, *, task_id):
            if not answers:
                raise PaperResearchError("no answers")
            ans = answers.pop(0)
            if isinstance(ans, Exception):
                raise ans
            return ans

        adapter.query_papers = AsyncMock(side_effect=_side_effect)
    return adapter


def _make_model_gateway() -> MagicMock:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(
        return_value='{"material_type":"background_reference","relationship_clear":true}'
    )
    return gateway


def _make_execute_context(
    session: Session,
    task_id: str,
    *,
    paper_adapter: MagicMock | None = None,
    model_gateway: MagicMock | None = None,
    web_adapter: MagicMock | None = None,
) -> ExecuteContext:
    event_bus = MagicMock()
    event_bus.publish = AsyncMock(return_value=MagicMock())
    ctx = ExecuteContext(
        task_id=task_id,
        event_bus=event_bus,
        evidence_service=EvidenceService(session),
        repo_adapter=MagicMock(),
        paper_adapter=paper_adapter or _make_paper_adapter(),
        web_adapter=web_adapter or MagicMock(),
        model_gateway=model_gateway or _make_model_gateway(),
        vector_store_factory=MagicMock(),
        sandbox_runner=MagicMock(),
    )
    register_context(task_id, ctx)
    return ctx


# ── _build_deep_research_questions ───────────────────────────────────────


def test_build_deep_research_questions_returns_four_questions() -> None:
    questions = _build_deep_research_questions(
        "对比 RAG 框架", ["LangChain", "LlamaIndex"]
    )
    assert len(questions) == 4
    assert any("核心结论" in q for q in questions)
    assert any("架构设计" in q for q in questions)
    assert any("工程成熟度" in q for q in questions)
    assert any("多方案选型" in q for q in questions)


def test_build_deep_research_questions_fallback_goal() -> None:
    questions = _build_deep_research_questions("", [])
    assert len(questions) == 4
    # 使用默认文案
    assert any("本次仓库调研目标" in q for q in questions)


# ── _query_paperqa_answers ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_paperqa_answers_writes_answer_records(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    answers, materials, evidence_ids = await _query_paperqa_answers(
        ctx,
        doc_paths=["paper.pdf"],
        questions=["这些资料的核心结论是什么？"],
        task_id=task_id,
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        repo_cards=[],
    )

    assert len(answers) == 1
    assert answers[0].question == "这些资料的核心结论是什么？"
    assert answers[0].answer == "综合回答"
    assert answers[0].failed is False
    assert len(answers[0].context_evidence_ids) >= 1
    assert answers[0].source_names == ["paper.pdf"]

    clear_context(task_id)


@pytest.mark.asyncio
async def test_query_paperqa_answers_multi_question(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    answers, materials, evidence_ids = await _query_paperqa_answers(
        ctx,
        doc_paths=["paper.pdf"],
        questions=["Q1", "Q2", "Q3", "Q4"],
        task_id=task_id,
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        repo_cards=[],
    )

    assert len(answers) == 4
    for a in answers:
        assert a.failed is False
        assert len(a.answer) > 0
        assert len(a.context_evidence_ids) >= 1

    clear_context(task_id)


@pytest.mark.asyncio
async def test_query_paperqa_answers_continues_on_single_failure(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    paper_adapter = _make_paper_adapter(
        answers=[
            PaperResearchError("Q1 failed"),
            PaperAnswer(
                answer="Q2 answer",
                contexts=[PaperContext(text="t2", source_name="s2", locator="l2")],
            ),
        ]
    )
    ctx = _make_execute_context(session, task_id, paper_adapter=paper_adapter)

    answers, materials, evidence_ids = await _query_paperqa_answers(
        ctx,
        doc_paths=["paper.pdf"],
        questions=["Q1", "Q2"],
        task_id=task_id,
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        repo_cards=[],
    )

    assert len(answers) == 2
    # Q1 失败
    assert answers[0].failed is True
    assert answers[0].warning == "Q1 failed"
    assert answers[0].answer == ""
    # Q2 成功
    assert answers[1].failed is False
    assert answers[1].answer == "Q2 answer"
    assert len(answers[1].context_evidence_ids) >= 1

    clear_context(task_id)


@pytest.mark.asyncio
async def test_query_paperqa_answers_all_failed(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    paper_adapter = _make_paper_adapter(
        answers=[
            PaperResearchError("all failed"),
        ]
    )
    ctx = _make_execute_context(session, task_id, paper_adapter=paper_adapter)

    answers, materials, evidence_ids = await _query_paperqa_answers(
        ctx,
        doc_paths=["paper.pdf"],
        questions=["Q1"],
        task_id=task_id,
        repo_urls=[],
        paper_urls=[],
        repo_cards=[],
    )

    assert len(answers) == 1
    assert answers[0].failed is True
    assert answers[0].warning == "all failed"

    clear_context(task_id)


@pytest.mark.asyncio
async def test_query_paperqa_answers_creates_evidence_for_contexts(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    _, materials, evidence_ids = await _query_paperqa_answers(
        ctx,
        doc_paths=["paper.pdf"],
        questions=["Q1"],
        task_id=task_id,
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        repo_cards=[],
    )

    # Evidence 被创建
    assert len(evidence_ids) >= 1
    # Materials 包含对应条目
    assert len(materials) >= 1
    assert materials[0].source_uri == "paper.pdf"
    assert materials[0].evidence_id in evidence_ids

    clear_context(task_id)


# ── paper_research 节点端到端（通过 engine + mock context） ─────────────


@pytest.mark.asyncio
async def test_paper_research_writes_paperqa_answers_to_seed(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "paper_urls": ["https://arxiv.org/abs/9999.99999"],
        "permissions": {"allow_web_search": False},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds, "paper_supplement seed should exist"
    seed = seeds[0]
    sd = seed.structured_data or {}
    assert "paperqa_answers" in sd
    answers = sd["paperqa_answers"]
    assert len(answers) >= 1
    # 至少有一个 answer 不为空且非失败
    assert any(a.get("answer") and not a.get("failed") for a in answers)

    clear_context(task_id)


@pytest.mark.asyncio
async def test_paper_research_narrative_contains_answer_summary(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "paper_urls": [],
        "permissions": {"allow_web_search": False},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds
    narrative = seeds[0].narrative_seed
    assert "PaperQA" in narrative
    assert "资料表明" in narrative or "综合回答" in narrative or "demo paper answer" in narrative

    clear_context(task_id)


@pytest.mark.asyncio
async def test_paper_research_writes_web_report_to_seed(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    # 构造带 web report 的 web_adapter
    web_adapter = MagicMock()
    web_adapter.research = AsyncMock(
        return_value=WebResearchResult(
            report="联网调研综合报告内容",
            sources=[WebSource(url="https://example.com", summary="ref")],
        )
    )
    ctx = _make_execute_context(session, task_id)
    ctx.web_adapter = web_adapter

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "paper_urls": [],
        "permissions": {"allow_web_search": True},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds
    sd = seeds[0].structured_data or {}
    assert "web_report" in sd
    assert sd["web_report"] == "联网调研综合报告内容"
    assert "web_sources" in sd
    assert len(sd["web_sources"]) >= 1

    clear_context(task_id)


@pytest.mark.asyncio
async def test_paper_research_web_report_in_narrative(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    web_adapter = MagicMock()
    web_adapter.research = AsyncMock(
        return_value=WebResearchResult(
            report="联网调研综合报告内容",
            sources=[WebSource(url="https://example.com", summary="ref")],
        )
    )
    ctx = _make_execute_context(session, task_id)
    ctx.web_adapter = web_adapter

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "paper_urls": [],
        "permissions": {"allow_web_search": True},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds
    narrative = seeds[0].narrative_seed
    assert "联网调研摘要" in narrative
    assert "联网调研综合报告内容" in narrative

    clear_context(task_id)


@pytest.mark.asyncio
async def test_paper_research_no_doc_paths_creates_pending_evidence(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ctx = _make_execute_context(session, task_id)

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": [],
        "paper_urls": ["https://arxiv.org/abs/9999.99999"],
        "permissions": {"allow_web_search": False},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds
    sd = seeds[0].structured_data or {}
    materials = sd.get("materials", [])
    # 应该至少有一个 pending material
    pending = [m for m in materials if m.get("material_type") == "unverified_reference"]
    assert len(pending) >= 1

    clear_context(task_id)


@pytest.mark.asyncio
async def test_paper_research_all_questions_failed_writes_warning(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    # 构造一个所有 question 都抛异常的 paper_adapter
    paper_adapter = MagicMock()
    paper_adapter.query_papers = AsyncMock(side_effect=PaperResearchError("all down"))
    ctx = _make_execute_context(session, task_id, paper_adapter=paper_adapter)

    state = {
        "task_id": task_id,
        "goal": "对比 RAG 框架",
        "repo_urls": [],
        "paper_urls": ["https://arxiv.org/abs/9999.99999"],
        "permissions": {"allow_web_search": False},
    }

    await paper_research(state)

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task_and_section(
            task_id, "paper_supplement"
        )
    assert seeds
    sd = seeds[0].structured_data or {}
    answers = sd.get("paperqa_answers", [])
    assert all(a.get("failed") for a in answers)
    assert seeds[0].warnings
    assert any("所有" in w and "失败" in w for w in seeds[0].warnings)

    clear_context(task_id)
