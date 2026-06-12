"""DemoMode 服务：幂等种子离线演示任务（F-014）。"""

from __future__ import annotations

from sqlmodel import Session

from ..demo.fixtures import DEMO_TASK_ID, build_demo_bundle
from ..models.task import TaskCreateResponse
from ..storage.repositories import (
    ComparisonRepository,
    EventRepository,
    EvidenceRepository,
    ReproducibilityRepository,
    ReportRepository,
    RepoCardRepository,
    TaskRepository,
)
from ..storage.tables import TaskTable
from ..models.enums import TaskStatus


class DemoService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_demo_task(self) -> TaskCreateResponse:
        """幂等写入 demo 任务及关联产物，返回固定 demo task_id。"""
        bundle = build_demo_bundle()
        task_data = bundle["task"]

        row = self.session.get(TaskTable, DEMO_TASK_ID)
        if row is None:
            row = TaskTable(**task_data)
            self.session.add(row)
        else:
            for key, value in task_data.items():
                setattr(row, key, value)
            self.session.add(row)
        self.session.commit()

        evidence_repo = EvidenceRepository(self.session)
        for item in bundle["evidence"]:
            if evidence_repo.get(item.id) is None:
                evidence_repo.create(item)

        repo_repo = RepoCardRepository(self.session)
        for card in bundle["repo_cards"]:
            if repo_repo.get(card.id) is None:
                repo_repo.create(card)

        ComparisonRepository(self.session).upsert_by_task(bundle["comparison"])
        ReproducibilityRepository(self.session).upsert_by_task(bundle["reproducibility"])
        ReportRepository(self.session).upsert_by_task(bundle["report"])

        event_repo = EventRepository(self.session)
        existing = event_repo.list_since(DEMO_TASK_ID, 0)
        if not existing:
            for event in bundle["node_events"]:
                event_repo.append(event)

        return TaskCreateResponse(task_id=DEMO_TASK_ID, status=TaskStatus.DONE)
