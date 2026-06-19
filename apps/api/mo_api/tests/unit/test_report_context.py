"""ReportContext 聚合单元测试（Phase A）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.enums import (
    ClaimLabel,
    EvidenceStrength,
    SourceType,
    TaskStatus,
)
from mo_api.models.evidence import EvidenceItem
from mo_api.models.task import TaskPermissions, TaskResponse
from mo_api.services.report_context import ReportContext, ReportContextService
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


def test_report_context_builds_task(engine) -> None:
    """context 至少包含 task 信息。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    with Session(engine) as session:
        service = ReportContextService(session)
        ctx = service.build(task_id)

    assert ctx.task.goal == "测试目标"
    assert ctx.task.status is TaskStatus.REPORT_DRAFT


def test_report_context_missing_task(engine) -> None:
    """不存在的 task_id 抛出 ValueError。"""
    with Session(engine) as session:
        service = ReportContextService(session)
        with pytest.raises(ValueError, match="task not found"):
            service.build("nonexistent-id")


def test_report_context_includes_plan_when_present(engine) -> None:
    """当 plan 存在时 context 应包含 plan。"""
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task(session, task_id)

    with Session(engine) as session:
        service = ReportContextService(session)
        ctx = service.build(task_id)

    # 无 plan 时应为 None
    assert ctx.plan is None
    assert isinstance(ctx.evidence_items, list)
    assert isinstance(ctx.repo_cards, list)
    assert isinstance(ctx.events, list)
