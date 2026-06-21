"""写入 ReportSectionSeed 的轻量服务。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from ..models.report import REPORT_SECTION_KEYS, REPORT_SECTION_TITLES
from ..models.report_seed import ReportSectionSeed
from ..storage.repositories import ReportSectionSeedRepository


class ReportSeedService:
    """为执行节点提供统一的章节 seed 写入入口。"""

    def __init__(self, session: Session) -> None:
        self.repo = ReportSectionSeedRepository(session)

    def upsert_seed(
        self,
        *,
        task_id: str,
        section_key: str,
        node: str,
        narrative_seed: str,
        title: str | None = None,
        structured_data: dict[str, Any] | None = None,
        evidence_ids: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> ReportSectionSeed:
        if section_key not in REPORT_SECTION_KEYS:
            raise ValueError(f"unknown report section key: {section_key}")

        now = datetime.now(timezone.utc)
        seed = ReportSectionSeed(
            id=uuid.uuid4().hex,
            task_id=task_id,
            section_key=section_key,
            node=node,
            title=title or REPORT_SECTION_TITLES.get(section_key, section_key),
            narrative_seed=(narrative_seed or "").strip()[:8000],
            structured_data=structured_data or {},
            evidence_ids=list(dict.fromkeys(evidence_ids or [])),
            warnings=list(dict.fromkeys(warnings or [])),
            created_at=now,
            updated_at=now,
        )
        return self.repo.upsert(seed)
