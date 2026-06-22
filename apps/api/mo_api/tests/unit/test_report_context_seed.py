"""ReportContext 中的 ReportSectionSeed 聚合测试。

覆盖：
- 基础 seed 聚合
- paperqa_answers 在 structured_data 中可读
- web_report 在 structured_data 中可读
- 多节点 seed 合并
- extract_seed_field 提取
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from mo_api.models.enums import TaskStatus
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.services.report_context import ReportContextService
from mo_api.services.research_synthesis import (
    extract_seed_field,
    extract_single_seed_field,
)
from mo_api.storage.repositories import ReportSectionSeedRepository
from mo_api.storage.tables import TaskTable


def _seed_task(session: Session, task_id: str) -> None:
    row = TaskTable(
        id=task_id,
        goal="测试目标",
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        output_language="zh",
        template=None,
        permissions={"allow_repo_clone": True},
        status=TaskStatus.REPORT_DRAFT.value,
    )
    session.add(row)
    session.commit()


def _seed_report_section(task_id: str) -> ReportSectionSeed:
    now = datetime.now(timezone.utc)
    return ReportSectionSeed(
        id="seed-1",
        task_id=task_id,
        section_key="repo_overview",
        node="repo_ingest",
        title="仓库概览",
        narrative_seed="repo overview seed",
        structured_data={"repo": "demo"},
        evidence_ids=["e1"],
        warnings=[],
        created_at=now,
        updated_at=now,
    )


def _seed_paper_supplement(task_id: str) -> ReportSectionSeed:
    now = datetime.now(timezone.utc)
    return ReportSectionSeed(
        id="seed-ps",
        task_id=task_id,
        section_key="paper_supplement",
        node="paper_research",
        title="论文/上下文补充",
        narrative_seed="paper supplement narrative",
        structured_data={
            "materials": [
                {"source_uri": "paper.pdf", "material_type": "official_repo_paper"},
            ],
            "paperqa_answers": [
                {
                    "question": "这些资料的核心结论是什么？",
                    "answer": "这些资料表明 Haystack 更偏 pipeline 工程化。",
                    "context_evidence_ids": ["ev1", "ev2"],
                    "source_names": ["docs/haystack.md"],
                    "failed": False,
                    "warning": None,
                },
                {
                    "question": "这些资料指出了哪些风险？",
                    "answer": "",
                    "context_evidence_ids": [],
                    "source_names": [],
                    "failed": True,
                    "warning": "查询超时",
                },
            ],
            "web_report": "联网调研综合报告内容摘要。",
            "web_sources": [
                {"url": "https://example.com/ref", "summary": "background ref"},
            ],
        },
        evidence_ids=["ev1", "ev2"],
        warnings=["存在资料关系不明项"],
        created_at=now,
        updated_at=now,
    )


# ── 基础聚合 ────────────────────────────────────────────────────────────


def test_report_context_includes_report_seeds(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_report_section(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    assert len(ctx.report_seeds) == 1
    assert ctx.report_seeds[0].section_key == "repo_overview"
    assert ctx.report_seeds[0].node == "repo_ingest"


# ── paperqa_answers 聚合 ────────────────────────────────────────────────


def test_report_context_reads_paperqa_answers(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    answers = extract_seed_field(ctx.report_seeds, "paperqa_answers")
    assert len(answers) == 2

    # 第一个回答成功
    assert answers[0]["question"] == "这些资料的核心结论是什么？"
    assert answers[0]["answer"] == "这些资料表明 Haystack 更偏 pipeline 工程化。"
    assert answers[0]["failed"] is False
    assert answers[0]["context_evidence_ids"] == ["ev1", "ev2"]

    # 第二个回答失败
    assert answers[1]["failed"] is True
    assert answers[1]["warning"] == "查询超时"


def test_report_context_reads_web_report(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    web_report = extract_single_seed_field(ctx.report_seeds, "web_report")
    assert web_report == "联网调研综合报告内容摘要。"


def test_report_context_reads_materials(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    materials = extract_seed_field(ctx.report_seeds, "materials")
    assert len(materials) >= 1
    assert materials[0]["source_uri"] == "paper.pdf"


def test_report_context_web_sources_aggregation(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    web_sources = extract_seed_field(ctx.report_seeds, "web_sources")
    assert len(web_sources) >= 1
    assert web_sources[0]["url"] == "https://example.com/ref"


# ── 多节点 seed 合并 ────────────────────────────────────────────────────


def test_report_context_merges_seeds_from_multiple_nodes(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        repo = ReportSectionSeedRepository(session)
        repo.upsert(_seed_report_section(task_id))
        repo.upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    assert len(ctx.report_seeds) == 2
    nodes = {s.node for s in ctx.report_seeds}
    assert nodes == {"repo_ingest", "paper_research"}
    sections = {s.section_key for s in ctx.report_seeds}
    assert sections == {"repo_overview", "paper_supplement"}


def test_report_context_seed_evidence_ids_preserved(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    seed = ctx.report_seeds[0]
    assert "ev1" in seed.evidence_ids
    assert "ev2" in seed.evidence_ids


def test_report_context_seed_warnings_preserved(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(_seed_paper_supplement(task_id))

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    seed = ctx.report_seeds[0]
    assert any("资料关系不明" in w for w in seed.warnings)


def test_report_context_empty_seeds(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)
        # 不写入任何 seed

    with Session(engine) as session:
        ctx = ReportContextService(session).build(task_id)

    assert ctx.report_seeds == []
