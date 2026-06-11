"""ReportService 单元测试（PRD F-011）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.enums import ClaimLabel, EvidenceStrength, SourceType, TaskStatus
from mo_api.models.evidence import EvidenceItem
from mo_api.models.report import REPORT_SECTION_KEYS
from mo_api.models.task import TaskPermissions, TaskResponse
from mo_api.services.report_service import ReportService
from mo_api.storage.repositories import TaskRepository
from mo_api.storage.tables import TaskTable


def _seed_reportable_task(session: Session, task_id: str) -> None:
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


@pytest.mark.asyncio
async def test_generate_async_pending_warnings(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)

    fake_gateway = MagicMock()
    fake_profile = MagicMock()
    fake_gateway.select.return_value = fake_profile
    fake_gateway.complete = AsyncMock(
        side_effect=lambda *a, **k: "LLM 叙述段落。"
    )

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    assert len(report.sections) == len(REPORT_SECTION_KEYS)
    assert any("M8" in w or "对比" in w for w in report.pending_warnings)
    assert any("M9" in w or "复现" in w for w in report.pending_warnings)
    assert "[pending]" in report.markdown or "[inference]" in report.markdown

    with Session(engine) as session:
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.REVIEW_REQUIRED


def test_evidence_to_label_mapping() -> None:
    service = ReportService(MagicMock())
    fact_item = EvidenceItem(
        id="e1",
        task_id="t1",
        source_type=SourceType.REPO_FILE,
        source_uri="https://github.com/o/r",
        locator="LICENSE",
        quote_or_summary="MIT",
        strength=EvidenceStrength.STRONG,
        created_at=datetime.now(timezone.utc),
    )
    infer_item = fact_item.model_copy(
        update={
            "id": "e2",
            "source_type": SourceType.MODEL_INFERENCE,
            "strength": EvidenceStrength.MEDIUM,
        }
    )
    assert service._evidence_to_label(fact_item) is ClaimLabel.FACT
    assert service._evidence_to_label(infer_item) is ClaimLabel.INFERENCE


def test_report_claim_validator_pending_without_evidence() -> None:
    from mo_api.models.evidence import ReportClaim

    claim = ReportClaim(
        id="c1",
        claim="待定项",
        label=ClaimLabel.PENDING,
        evidence_ids=[],
    )
    assert claim.label is ClaimLabel.PENDING

    with pytest.raises(ValueError, match="evidence_ids"):
        ReportClaim(
            id="c2",
            claim="无证据事实",
            label=ClaimLabel.FACT,
            evidence_ids=[],
        )


@pytest.mark.asyncio
async def test_generate_handles_llm_failure(engine) -> None:
    """LLM 调用失败时 generate_async 应仍返回 report（LLM 段 fallback 为 PENDING）。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)

    fake_gateway = MagicMock()
    fake_profile = MagicMock()
    fake_gateway.select.return_value = fake_profile
    fake_gateway.complete = AsyncMock(
        side_effect=Exception("LLM timeout")
    )

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        # 不应抛异常——LLM 错误应被处理为 fallback
        report = await service.generate_async(task_id)

    assert len(report.sections) == len(REPORT_SECTION_KEYS)
    assert len(report.markdown) > 0


@pytest.mark.asyncio
async def test_task_background_claim_is_fact(engine) -> None:
    """FIX-1: task_background 的目标 claim 应标 fact 而非 pending。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)

    fake_gateway = MagicMock()
    fake_gateway.select.return_value = MagicMock()
    fake_gateway.complete = AsyncMock(return_value="叙述。")

    with Session(engine) as session:
        service = ReportService(session, gateway=fake_gateway)
        report = await service.generate_async(task_id)

    bg_section = next(
        s for s in report.sections if s.key == "task_background"
    )
    fact_claims = [c for c in bg_section.claims if c.label == ClaimLabel.FACT]
    assert len(fact_claims) >= 1
    assert any("调研目标" in c.claim for c in fact_claims)
