"""ReportContext 聚合：统一拉取报告生成所需的所有数据。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.comparison import ComparisonMatrix
from ..models.events import NodeEvent
from ..models.evidence import EvidenceItem
from ..models.plan import Plan
from ..models.repo import RepoCard
from ..models.report_seed import ReportSectionSeed
from ..models.reproducibility import ReproducibilityReport
from ..models.task import TaskResponse
from ..storage.repositories import (
    ComparisonRepository,
    EventRepository,
    EvidenceRepository,
    PlanRepository,
    ReportSectionSeedRepository,
    ReproducibilityRepository,
    RepoCardRepository,
    TaskRepository,
)


class ReportContext(BaseModel):
    """一次报告生成的全部输入数据。"""

    task: TaskResponse
    plan: Plan | None = None
    events: list[NodeEvent] = Field(default_factory=list)
    repo_cards: list[RepoCard] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    comparison: ComparisonMatrix | None = None
    reproducibility: ReproducibilityReport | None = None
    report_seeds: list[ReportSectionSeed] = Field(default_factory=list)


class ReportContextService:
    """从各 Repository 聚合 ReportContext。"""

    def __init__(self, session) -> None:
        self.session = session

    def build(self, task_id: str) -> ReportContext:
        task_repo = TaskRepository(self.session)
        task = task_repo.get(task_id)
        if task is None:
            raise ValueError("task not found")
        return ReportContext(
            task=task,
            plan=PlanRepository(self.session).get_latest_by_task(task_id),
            events=EventRepository(self.session).list_since(task_id, 0),
            repo_cards=RepoCardRepository(self.session).list_by_task(task_id),
            evidence_items=EvidenceRepository(self.session).list_by_task(task_id),
            comparison=ComparisonRepository(self.session).get_by_task(task_id),
            reproducibility=ReproducibilityRepository(self.session).get_by_task(task_id),
            report_seeds=ReportSectionSeedRepository(self.session).list_by_task(task_id),
        )
