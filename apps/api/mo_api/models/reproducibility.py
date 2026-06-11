"""复现评估领域模型（PRD F-007）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import REPRO_DIMENSIONS, STATIC_REPRO_ASSESSMENT_LABEL, MaterialType


class PaperMaterial(BaseModel):
    """论文/资料条目（PRD F-006）。"""

    source_uri: str
    material_type: MaterialType
    evidence_id: str
    related_repo_url: str | None = None
    relationship_clear: bool = False
    summary: str = ""


class ReproducibilityScore(BaseModel):
    """单仓库复现评分（PRD F-007）。"""

    repo_url: str
    repo_name: str
    overall_score: float = Field(ge=0.0, le=1.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    recommended_next_checks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assessment_label: str = STATIC_REPRO_ASSESSMENT_LABEL


class ReproducibilityReport(BaseModel):
    """任务级复现评估报告。"""

    id: str
    task_id: str
    scores: list[ReproducibilityScore] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=lambda: list(REPRO_DIMENSIONS))
    generated_at: datetime
