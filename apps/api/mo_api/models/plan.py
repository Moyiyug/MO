"""PlanMode 数据模型（PRD F-002）。"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import PlanStepStatus, PlanStepTool, RiskLevel
from .repo_discovery import RepoCandidate

DEFAULT_RUBRIC_WEIGHTS: dict[str, float] = {
    "reproducibility": 0.30,
    "documentation": 0.20,
    "research_value": 0.20,
    "engineering_fit": 0.20,
    "extensibility": 0.10,
}


class ClarifyingQuestion(BaseModel):
    id: str
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str | None = None
    required: bool = False


class PlanStep(BaseModel):
    id: str
    node_id: str  # 对应 ExecuteMode 图中 WorkflowNode 的节点 ID（F-002）
    title: str
    description: str
    tool: PlanStepTool
    risk_level: RiskLevel
    requires_approval: bool
    expected_outputs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    user_editable: bool = True
    status: PlanStepStatus = PlanStepStatus.PENDING


class ReportRubric(BaseModel):
    weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_RUBRIC_WEIGHTS))

    @model_validator(mode="after")
    def _weights_sum(self) -> ReportRubric:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"rubric weights must sum to ~1.0, got {total}")
        return self


class Plan(BaseModel):
    id: str
    task_id: str
    task_summary: str
    confirmed_context: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    proposed_steps: list[PlanStep] = Field(default_factory=list)
    report_rubric: ReportRubric = Field(default_factory=ReportRubric)
    risk_summary: list[str] = Field(default_factory=list)
    approval_required: bool = True
    # F-015：候选仓库清单（PlanMode 中供用户确认后写回 task.repo_urls）
    repo_candidates: list[RepoCandidate] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClarificationAnswer(BaseModel):
    question_id: str
    answer: str = Field(min_length=1)


class ClarificationsRequest(BaseModel):
    answers: list[ClarificationAnswer] = Field(min_length=1)


class ApprovePlanRequest(BaseModel):
    rubric_weights: dict[str, float] | None = None
    disabled_step_ids: list[str] = Field(default_factory=list)

    @field_validator("rubric_weights")
    @classmethod
    def _validate_weights(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return v
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"rubric weights must sum to ~1.0, got {total}")
        return v


class ReplanRequest(BaseModel):
    reason: str | None = None


class PlanResponse(Plan):
    """API 响应：与 Plan 相同。"""


class ApprovePlanResponse(BaseModel):
    plan: Plan
    status: str
