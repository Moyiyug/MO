"""证据链领域模型（PRD F-009）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from .enums import ClaimLabel, EvidenceStrength, MaterialType, SourceType


class EvidenceItem(BaseModel):
    """单条证据（PRD F-009）。"""

    id: str
    task_id: str
    source_type: SourceType
    source_uri: str
    locator: str | None = None
    quote_or_summary: str
    strength: EvidenceStrength = EvidenceStrength.MEDIUM
    material_type: MaterialType | None = None
    used_by: list[str] = Field(default_factory=list)
    created_at: datetime


class ReportClaim(BaseModel):
    """报告论断（PRD F-009 / MO_Backend §4）。"""

    id: str
    claim: str
    label: ClaimLabel
    confidence: float = 0.5
    evidence_ids: list[str] = Field(default_factory=list)
    requires_user_review: bool = False

    @model_validator(mode="after")
    def _evidence_required(self) -> ReportClaim:
        if self.label is not ClaimLabel.PENDING and not self.evidence_ids:
            raise ValueError("non-pending claim must have evidence_ids")
        return self
