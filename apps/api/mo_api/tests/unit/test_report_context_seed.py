"""ReportContext 中的 ReportSectionSeed 聚合测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from mo_api.models.enums import TaskStatus
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.services.report_context import ReportContextService
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
