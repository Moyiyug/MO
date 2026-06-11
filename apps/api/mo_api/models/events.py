"""工作流节点事件模型（PRD F-010）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import NodeStatus


class NodeEvent(BaseModel):
    """SSE 推送的节点事件。"""

    task_id: str
    seq: int
    node: str
    status: NodeStatus
    input_summary: str | None = None
    output_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    error_message: str | None = None
    next_action: str | None = None
    created_at: datetime


class StepApproveRequest(BaseModel):
    approved: bool


class ExecuteResponse(BaseModel):
    task_id: str
    status: str


class StepApproveResponse(BaseModel):
    task_id: str
    step_id: str
    status: str
