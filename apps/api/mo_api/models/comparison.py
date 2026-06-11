"""多仓库对比领域模型（PRD F-008）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .enums import ClaimLabel
from .plan import DEFAULT_RUBRIC_WEIGHTS

# PRD F-008 默认 8 个对比维度
COMPARISON_DIMENSIONS: list[str] = [
    "technical_route",
    "documentation",
    "reproducibility",
    "engineering_fit",
    "research_value",
    "extensibility",
    "risks",
    "recommended_use_case",
]

# 参与加权总分的维度（与 report_rubric 一致）
WEIGHTED_DIMENSIONS: list[str] = list(DEFAULT_RUBRIC_WEIGHTS.keys())


class DimensionScore(BaseModel):
    """单仓库单维度评分。"""

    dimension: str
    repo_url: str
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    label: ClaimLabel = ClaimLabel.INFERENCE

    @field_validator("score")
    @classmethod
    def _clamp_score(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class RepoRanking(BaseModel):
    """仓库加权排名。"""

    repo_url: str
    repo_name: str
    weighted_total: float
    per_dimension: dict[str, float] = Field(default_factory=dict)


class ComparisonMatrix(BaseModel):
    """多仓库对比矩阵（PRD F-008）。"""

    id: str
    task_id: str
    repo_urls: list[str]
    dimensions: list[str] = Field(default_factory=lambda: list(COMPARISON_DIMENSIONS))
    weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_RUBRIC_WEIGHTS)
    )
    scores: list[DimensionScore] = Field(default_factory=list)
    rankings: list[RepoRanking] = Field(default_factory=list)
    recommendation: str = ""
    limitations: list[str] = Field(default_factory=list)
    recommendation_evidence_ids: list[str] = Field(default_factory=list)
    generated_at: datetime

    @field_validator("weights")
    @classmethod
    def _weights_sum(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"weights must sum to ~1.0, got {total}")
        return v


class RecomputeComparisonRequest(BaseModel):
    """出报告前重算权重请求。"""

    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def _validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        total = sum(v.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"weights must sum to ~1.0, got {total}")
        return v
