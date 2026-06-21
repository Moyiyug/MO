"""报告章节种子模型：执行节点写入，ReportService 后续读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportSectionSeed(BaseModel):
    """执行节点产出的章节叙事种子。

    它不是最终报告，也不是 claim；当前阶段仅持久化为后续 Report B
    章节润色/总编流程提供输入。
    """

    id: str
    task_id: str
    section_key: str
    node: str
    title: str
    narrative_seed: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
