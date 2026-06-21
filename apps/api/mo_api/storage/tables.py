"""SQLModel 表定义。

列表 / 字典字段用 JSON 列存储（SQLite 原生支持 JSON 文本）。
表模型与 API 模型分离：API 层用 models/task.py 的 Pydantic 模型。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskTable(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(primary_key=True)
    goal: str
    repo_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    paper_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    output_language: str = "zh"
    template: str | None = None
    permissions: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class PlanTable(SQLModel, table=True):
    __tablename__ = "plans"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    version: int = Field(index=True)
    thread_id: str
    plan_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    approved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)


class RepoCardTable(SQLModel, table=True):
    __tablename__ = "repo_cards"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    repo_url: str = Field(index=True)
    card_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class EvidenceTable(SQLModel, table=True):
    __tablename__ = "evidence_items"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    source_uri: str = Field(index=True)
    locator: str | None = Field(default=None, index=True)
    evidence_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)


class ComparisonTable(SQLModel, table=True):
    __tablename__ = "comparisons"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True, unique=True)
    comparison_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=_utcnow)


class ReproducibilityTable(SQLModel, table=True):
    __tablename__ = "reproducibility_reports"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True, unique=True)
    report_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=_utcnow)


class ReportTable(SQLModel, table=True):
    __tablename__ = "reports"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True, unique=True)
    report_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=_utcnow)


class ReportSectionSeedTable(SQLModel, table=True):
    """报告章节种子持久化表。"""

    __tablename__ = "report_section_seeds"

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    section_key: str = Field(index=True)
    node: str = Field(index=True)
    seed_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = None


class NodeEventTable(SQLModel, table=True):
    __tablename__ = "node_events"
    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_node_events_task_seq"),
    )

    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    seq: int = Field(index=True)
    node: str
    status: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_utcnow)
