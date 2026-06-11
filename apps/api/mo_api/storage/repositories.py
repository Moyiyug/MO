"""数据访问层（Repository）。

负责 TaskTable（DB 行）与 TaskResponse（API 模型）之间的映射。
上层 service 不直接接触 SQLModel 会话之外的 ORM 细节。
"""

from __future__ import annotations

import threading
import uuid

from sqlmodel import Session, select

from ..models.enums import OutputLanguage, TaskStatus
from ..models.evidence import EvidenceItem
from ..models.events import NodeEvent
from ..models.plan import Plan
from ..models.report import Report
from ..models.repo import RepoCard
from ..models.task import TaskPermissions, TaskResponse
from .tables import (
    EvidenceTable,
    NodeEventTable,
    PlanTable,
    RepoCardTable,
    ReportTable,
    TaskTable,
)


def _to_response(row: TaskTable) -> TaskResponse:
    return TaskResponse(
        task_id=row.id,
        goal=row.goal,
        status=TaskStatus(row.status),
        repo_urls=list(row.repo_urls or []),
        paper_urls=list(row.paper_urls or []),
        output_language=OutputLanguage(row.output_language),
        template=row.template,
        permissions=TaskPermissions(**(row.permissions or {})),
        created_at=row.created_at,
    )


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, row: TaskTable) -> TaskResponse:
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_response(row)

    def list(self) -> list[TaskResponse]:
        rows = self.session.exec(
            select(TaskTable).order_by(TaskTable.created_at.desc())
        ).all()
        return [_to_response(r) for r in rows]

    def get(self, task_id: str) -> TaskResponse | None:
        row = self.session.get(TaskTable, task_id)
        return _to_response(row) if row else None

    def update_status(self, task_id: str, status: TaskStatus) -> TaskResponse | None:
        row = self.session.get(TaskTable, task_id)
        if row is None:
            return None
        row.status = status.value
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _to_response(row)


class PlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def count_by_task(self, task_id: str) -> int:
        rows = self.session.exec(
            select(PlanTable).where(PlanTable.task_id == task_id)
        ).all()
        return len(rows)

    def create(
        self,
        *,
        plan: Plan,
        version: int,
        thread_id: str,
        approved: bool = False,
    ) -> Plan:
        row = PlanTable(
            id=plan.id,
            task_id=plan.task_id,
            version=version,
            thread_id=thread_id,
            plan_data=plan.model_dump(mode="json"),
            approved=approved,
            created_at=plan.created_at,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Plan.model_validate(row.plan_data)

    def get_latest_by_task(self, task_id: str) -> Plan | None:
        row = self.session.exec(
            select(PlanTable)
            .where(PlanTable.task_id == task_id)
            .order_by(PlanTable.version.desc())
        ).first()
        if row is None:
            return None
        return Plan.model_validate(row.plan_data)

    def get_latest_row(self, task_id: str) -> PlanTable | None:
        return self.session.exec(
            select(PlanTable)
            .where(PlanTable.task_id == task_id)
            .order_by(PlanTable.version.desc())
        ).first()

    def update_plan_data(self, plan_id: str, plan_data: dict, *, approved: bool) -> Plan | None:
        row = self.session.get(PlanTable, plan_id)
        if row is None:
            return None
        row.plan_data = plan_data
        row.approved = approved
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return Plan.model_validate(row.plan_data)


def _event_to_row(event: NodeEvent) -> NodeEventTable:
    return NodeEventTable(
        id=uuid.uuid4().hex,
        task_id=event.task_id,
        seq=event.seq,
        node=event.node,
        status=event.status.value,
        payload=event.model_dump(mode="json"),
        created_at=event.created_at,
    )


def _row_to_event(row: NodeEventTable) -> NodeEvent:
    data = dict(row.payload or {})
    data.setdefault("task_id", row.task_id)
    data.setdefault("seq", row.seq)
    data.setdefault("node", row.node)
    data.setdefault("status", row.status)
    data.setdefault("created_at", row.created_at)
    return NodeEvent.model_validate(data)


class EventRepository:
    _append_lock = threading.Lock()

    def __init__(self, session: Session) -> None:
        self.session = session

    def max_seq(self, task_id: str) -> int:
        rows = self.session.exec(
            select(NodeEventTable.seq)
            .where(NodeEventTable.task_id == task_id)
            .order_by(NodeEventTable.seq.desc())
        ).first()
        return rows if rows is not None else 0

    def append(self, event: NodeEvent) -> NodeEvent:
        with self._append_lock:
            next_seq = self.max_seq(event.task_id) + 1
            saved = event.model_copy(update={"seq": next_seq})
            row = _event_to_row(saved)
            self.session.add(row)
            self.session.commit()
            self.session.refresh(row)
            return _row_to_event(row)

    def list_since(self, task_id: str, since_seq: int) -> list[NodeEvent]:
        rows = self.session.exec(
            select(NodeEventTable)
            .where(NodeEventTable.task_id == task_id)
            .where(NodeEventTable.seq > since_seq)
            .order_by(NodeEventTable.seq.asc())
        ).all()
        return [_row_to_event(r) for r in rows]


def _row_to_repo_card(row: RepoCardTable) -> RepoCard:
    data = dict(row.card_data or {})
    data.setdefault("id", row.id)
    data.setdefault("task_id", row.task_id)
    data.setdefault("repo_url", row.repo_url)
    return RepoCard.model_validate(data)


class RepoCardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, card: RepoCard) -> RepoCard:
        row = RepoCardTable(
            id=card.id,
            task_id=card.task_id,
            repo_url=card.repo_url,
            card_data=card.model_dump(mode="json"),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_repo_card(row)

    def get(self, card_id: str) -> RepoCard | None:
        row = self.session.get(RepoCardTable, card_id)
        return _row_to_repo_card(row) if row else None

    def list_by_task(self, task_id: str) -> list[RepoCard]:
        rows = self.session.exec(
            select(RepoCardTable)
            .where(RepoCardTable.task_id == task_id)
            .order_by(RepoCardTable.created_at.asc())
        ).all()
        return [_row_to_repo_card(r) for r in rows]

    def exists_for_repo(self, task_id: str, repo_url: str) -> bool:
        row = self.session.exec(
            select(RepoCardTable)
            .where(RepoCardTable.task_id == task_id)
            .where(RepoCardTable.repo_url == repo_url)
        ).first()
        return row is not None


def _row_to_evidence(row: EvidenceTable) -> EvidenceItem:
    data = dict(row.evidence_data or {})
    data.setdefault("id", row.id)
    data.setdefault("task_id", row.task_id)
    data.setdefault("source_uri", row.source_uri)
    data.setdefault("locator", row.locator)
    return EvidenceItem.model_validate(data)


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, item: EvidenceItem) -> EvidenceItem:
        row = EvidenceTable(
            id=item.id,
            task_id=item.task_id,
            source_uri=item.source_uri,
            locator=item.locator,
            evidence_data=item.model_dump(mode="json"),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_evidence(row)

    def get(self, evidence_id: str) -> EvidenceItem | None:
        row = self.session.get(EvidenceTable, evidence_id)
        return _row_to_evidence(row) if row else None

    def find_by_locator(
        self, task_id: str, source_uri: str, locator: str | None
    ) -> EvidenceItem | None:
        query = (
            select(EvidenceTable)
            .where(EvidenceTable.task_id == task_id)
            .where(EvidenceTable.source_uri == source_uri)
        )
        if locator is None:
            query = query.where(EvidenceTable.locator.is_(None))
        else:
            query = query.where(EvidenceTable.locator == locator)
        row = self.session.exec(query).first()
        return _row_to_evidence(row) if row else None

    def list_by_task(self, task_id: str) -> list[EvidenceItem]:
        rows = self.session.exec(
            select(EvidenceTable)
            .where(EvidenceTable.task_id == task_id)
            .order_by(EvidenceTable.created_at.asc())
        ).all()
        return [_row_to_evidence(r) for r in rows]

    def update_used_by(self, evidence_id: str, used_by: list[str]) -> EvidenceItem | None:
        row = self.session.get(EvidenceTable, evidence_id)
        if row is None:
            return None
        data = dict(row.evidence_data or {})
        data["used_by"] = used_by
        row.evidence_data = data
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_evidence(row)


def _row_to_report(row: ReportTable) -> Report:
    data = dict(row.report_data or {})
    data.setdefault("id", row.id)
    data.setdefault("task_id", row.task_id)
    data.setdefault("generated_at", row.generated_at)
    return Report.model_validate(data)


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_task(self, task_id: str) -> Report | None:
        row = self.session.exec(
            select(ReportTable).where(ReportTable.task_id == task_id)
        ).first()
        return _row_to_report(row) if row else None

    def upsert_by_task(self, report: Report) -> Report:
        existing = self.session.exec(
            select(ReportTable).where(ReportTable.task_id == report.task_id)
        ).first()
        if existing is None:
            row = ReportTable(
                id=report.id,
                task_id=report.task_id,
                report_data=report.model_dump(mode="json"),
                generated_at=report.generated_at,
            )
            self.session.add(row)
        else:
            existing.report_data = report.model_dump(mode="json")
            existing.generated_at = report.generated_at
            self.session.add(existing)
        self.session.commit()
        if existing is None:
            self.session.refresh(row)
            return _row_to_report(row)
        self.session.refresh(existing)
        return _row_to_report(existing)
