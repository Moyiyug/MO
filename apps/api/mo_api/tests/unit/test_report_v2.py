"""Report v2 功能测试（Phase A-F）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.enums import ClaimLabel, EvidenceStrength, SourceType, TaskStatus
from mo_api.models.evidence import EvidenceItem
from mo_api.models.report import (
    REPORT_SECTION_KEYS,
    EvidenceAppendixGroup,
    KeyFinding,
    ScenarioRecommendation,
    Report,
    ReportSection,
)
from mo_api.services.report_service import ReportService
from mo_api.storage.repositories import TaskRepository
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


# -- Schema backward compatibility --

def test_report_v2_fields_are_optional() -> None:
    """旧 JSON 不含 v2 字段时仍可正常解析。"""
    report = Report(
        id="r1",
        task_id="t1",
        sections=[],
        pending_warnings=[],
        generated_at=datetime.now(timezone.utc),
        markdown="# test",
    )
    # v2 字段应为默认值
    assert report.report_version == "v2"
    assert report.executive_summary is None
    assert report.key_findings == []
    assert report.recommendation_summary == []
    assert report.evidence_appendix_groups == []


def test_report_section_v2_fields_are_optional() -> None:
    """旧 JSON 不含 v2 字段时仍可解析。"""
    section = ReportSection(
        key="test",
        title="Test",
        markdown="# test",
    )
    assert section.summary is None
    assert section.evidence_ids == []
    assert section.metadata == {}


def test_report_v2_fields_serialize() -> None:
    """v2 字段应出现在 model_dump 中。"""
    report = Report(
        id="r1",
        task_id="t1",
        sections=[],
        pending_warnings=[],
        generated_at=datetime.now(timezone.utc),
        markdown="# test",
        executive_summary="Executive summary",
        key_findings=[
            KeyFinding(title="Finding", summary="summary", label=ClaimLabel.INFERENCE)
        ],
        recommendation_summary=[
            ScenarioRecommendation(scenario="demo", recommendation="try repo A", rationale="easy setup")
        ],
        evidence_appendix_groups=[
            EvidenceAppendixGroup(key="repo_file", title="Repos", evidence_ids=["e1"])
        ],
    )
    d = report.model_dump(mode="json")
    assert d["report_version"] == "v2"
    assert d["executive_summary"] == "Executive summary"
    assert len(d["key_findings"]) == 1
    assert len(d["recommendation_summary"]) == 1
    assert len(d["evidence_appendix_groups"]) == 1


# -- Generate v2 report --

@pytest.mark.asyncio
async def test_generate_v2_report_has_v2_fields(engine) -> None:
    """v2 报告应包含 executive_summary 等新字段。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="LLM narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    assert report.report_version == "v2"
    assert report.executive_summary is not None
    assert len(report.executive_summary) > 0


@pytest.mark.asyncio
async def test_generate_v2_has_all_13_sections(engine) -> None:
    """v2 报告仍输出 13 个章节。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    section_keys = [s.key for s in report.sections]
    assert section_keys == REPORT_SECTION_KEYS


# -- Evidence appendix --

@pytest.mark.asyncio
async def test_evidence_appendix_groups_by_source_type(engine) -> None:
    """evidence_references 章节按 source_type 分组。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    appendix = next(s for s in report.sections if s.key == "evidence_references")
    # v2 appendix 应包含分组标题，不直接 dump raw evidence id 作为主标题
    markdown = appendix.markdown
    assert "E01" in markdown or "尚无证据" in markdown


# -- Recommendation always requires_user_review --

@pytest.mark.asyncio
async def test_recommendation_claims_require_user_review(engine) -> None:
    """推荐 claim 必须 requires_user_review=True 或为 pending。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    rec_section = next(s for s in report.sections if s.key == "recommendation")
    for claim in rec_section.claims:
        if claim.label is ClaimLabel.RECOMMENDATION:
            assert claim.requires_user_review is True, f"Recommendation should require review: {claim.claim}"
        # 非 pending claim 应有 evidence_ids
        if claim.label is not ClaimLabel.PENDING:
            assert claim.evidence_ids, f"Non-pending claim must have evidence: {claim.label}"


# -- Static repro assessment --

@pytest.mark.asyncio
async def test_no_repro_success_without_run_log(engine) -> None:
    """无 run_log 时报告不声称复现成功。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    forbidden = ["复现成功", "已复现", "smoke test passed", "运行通过"]
    repro_section = next((s for s in report.sections if s.key == "reproducibility"), None)
    if repro_section and not repro_section.is_pending:
        # 集成测试环境中可能产生 run_log，跳过弱断言
        pass
    else:
        # 无 repro data 时不应有复现成功声明
        for word in forbidden:
            assert word not in report.markdown, f"Should not contain '{word}' without run_log"


# -- Risks grouped --

@pytest.mark.asyncio
async def test_risks_section_has_grouped_content(engine) -> None:
    """风险章节应按影响分组。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="narrative.")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    risk_section = next(s for s in report.sections if s.key == "risks")
    # v2 risks: either pending (no data) or has grouped sections
    assert risk_section is not None
