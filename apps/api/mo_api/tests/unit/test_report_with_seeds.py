"""ReportService seed + polish integration tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.enums import ClaimLabel, TaskStatus
from mo_api.models.report import REPORT_SECTION_KEYS
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.services.report_service import ReportService
from mo_api.storage.repositories import ReportSectionSeedRepository
from mo_api.storage.tables import TaskTable


def _seed_reportable_task(session: Session, task_id: str) -> None:
    session.add(
        TaskTable(
            id=task_id,
            goal="测试目标",
            repo_urls=["https://github.com/owner/repo-a"],
            paper_urls=[],
            output_language="zh",
            template=None,
            permissions={"allow_repo_clone": True},
            status=TaskStatus.REPORT_DRAFT.value,
        )
    )
    session.commit()


def _fake_gateway() -> MagicMock:
    async def _complete(profile, messages, **kwargs):
        content = messages[0]["content"]
        if "MO 报告章节编辑器" in content:
            return (
                '{"summary":"摘要","reader_markdown":"润色后的正文","warnings":[]}'
            )
        if "MO 最终报告编辑器" in content:
            return '{"reader_markdown":"not a full report"}'
        if "执行摘要" in content or "execution summary" in content.lower():
            return "执行叙述。"
        if "技术路线" in content or "technical route" in content.lower():
            return "技术叙述。"
        return "叙述。"

    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(side_effect=_complete)
    return gateway


@pytest.mark.asyncio
async def test_report_sections_preserve_structured_markdown_and_seed_metadata(
    engine,
) -> None:
    task_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(
            ReportSectionSeed(
                id=uuid.uuid4().hex,
                task_id=task_id,
                section_key="repo_overview",
                node="repo_ingest",
                title="仓库概览",
                narrative_seed="这是节点阶段生成的仓库概览种子。",
                structured_data={"repo_count": 1},
                evidence_ids=[],
                warnings=[],
                created_at=now,
                updated_at=now,
            )
        )

    with Session(engine) as session:
        report = await ReportService(
            session,
            gateway=_fake_gateway(),
        ).generate_async(task_id)

    assert [section.key for section in report.sections] == REPORT_SECTION_KEYS

    section = next(s for s in report.sections if s.key == "repo_overview")
    assert section.markdown == "润色后的正文"
    assert section.metadata["structured_markdown"]
    assert section.metadata["seed_narratives"] == [
        "这是节点阶段生成的仓库概览种子。"
    ]
    assert section.metadata["seed_nodes"] == ["repo_ingest"]
    assert section.metadata["seed_structured_data"] == [{"repo_count": 1}]
    assert section.metadata["polish_status"] == "polished"

    background = next(s for s in report.sections if s.key == "task_background")
    assert len(background.claims) == 1
    assert background.claims[0].label is ClaimLabel.FACT
    assert background.claims[0].evidence_ids == background.evidence_ids
    assert background.markdown == "润色后的正文"


@pytest.mark.asyncio
async def test_report_polish_keeps_order_and_repro_boundary(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)

    with Session(engine) as session:
        report = await ReportService(
            session,
            gateway=_fake_gateway(),
        ).generate_async(task_id)

    assert [section.key for section in report.sections] == REPORT_SECTION_KEYS
    assert len(report.sections) == 13
    for section in report.sections:
        assert "structured_markdown" in section.metadata
        assert section.metadata["polish_status"] == "polished"

    reproducibility = next(
        section for section in report.sections if section.key == "reproducibility"
    )
    assert "复现成功" not in reproducibility.markdown
    assert "复现成功" not in report.markdown
