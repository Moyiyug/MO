"""SQLModel 表定义。

列表 / 字典字段用 JSON 列存储（SQLite 原生支持 JSON 文本）。
表模型与 API 模型分离：API 层用 models/task.py 的 Pydantic 模型。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column
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
