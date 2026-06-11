"""证据链业务服务（PRD F-009）。"""

from __future__ import annotations

from sqlmodel import Session

from ..models.evidence import EvidenceItem
from ..storage.repositories import EvidenceRepository


class EvidenceService:
    def __init__(self, session: Session) -> None:
        self._repo = EvidenceRepository(session)

    def add(self, item: EvidenceItem) -> str:
        """写入证据；按 task_id+source_uri+locator 去重，返回已有或新建 id。"""
        existing = self._repo.find_by_locator(
            item.task_id, item.source_uri, item.locator
        )
        if existing is not None:
            return existing.id
        saved = self._repo.create(item)
        return saved.id

    def list_by_task(self, task_id: str) -> list[EvidenceItem]:
        return self._repo.list_by_task(task_id)

    def link_used_by(self, evidence_id: str, consumer_id: str) -> None:
        item = self._repo.get(evidence_id)
        if item is None:
            return
        used_by = list(item.used_by)
        if consumer_id not in used_by:
            used_by.append(consumer_id)
            self._repo.update_used_by(evidence_id, used_by)
