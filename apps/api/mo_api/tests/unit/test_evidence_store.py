"""EvidenceService 与 TaskVectorStore 单元测试。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import EvidenceStrength, SourceType
from mo_api.models.evidence import EvidenceItem
from mo_api.services.evidence_service import EvidenceService
from mo_api.storage.vector_store import TaskVectorStore


def _item(task_id: str, *, locator: str = "README.md") -> EvidenceItem:
    return EvidenceItem(
        id=uuid.uuid4().hex,
        task_id=task_id,
        source_type=SourceType.REPO_FILE,
        source_uri="https://github.com/o/r",
        locator=locator,
        quote_or_summary="summary",
        strength=EvidenceStrength.STRONG,
        created_at=datetime.now(timezone.utc),
    )


def test_evidence_dedup_by_locator(engine) -> None:
    task_id = "ev-task"
    with Session(engine) as session:
        service = EvidenceService(session)
        first = _item(task_id)
        second = _item(task_id)
        id1 = service.add(first)
        id2 = service.add(second)
        assert id1 == id2
        assert len(service.list_by_task(task_id)) == 1


def test_link_used_by_appends_once(engine) -> None:
    task_id = "ev-link"
    with Session(engine) as session:
        service = EvidenceService(session)
        eid = service.add(_item(task_id))
        service.link_used_by(eid, "repo_card")
        service.link_used_by(eid, "repo_card")
        items = service.list_by_task(task_id)
        assert items[0].used_by == ["repo_card"]


def test_find_by_locator_none_matches_null_locator(engine) -> None:
    """locator=None 的去重应仅匹配 locator 为 NULL 的记录。"""
    from mo_api.storage.repositories import EvidenceRepository

    task_id = "ev-null"
    with Session(engine) as session:
        repo = EvidenceRepository(session)
        item_with = EvidenceItem(
            id=uuid.uuid4().hex,
            task_id=task_id,
            source_type=SourceType.REPO_FILE,
            source_uri="https://github.com/o/r",
            locator="README.md",
            quote_or_summary="with locator",
            strength=EvidenceStrength.STRONG,
            created_at=datetime.now(timezone.utc),
        )
        item_without = EvidenceItem(
            id=uuid.uuid4().hex,
            task_id=task_id,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri="https://github.com/o/r",
            locator=None,
            quote_or_summary="without locator",
            strength=EvidenceStrength.MEDIUM,
            created_at=datetime.now(timezone.utc),
        )
        repo.create(item_with)
        repo.create(item_without)

        found = repo.find_by_locator(task_id, "https://github.com/o/r", None)
        assert found is not None
        assert found.locator is None
        assert found.quote_or_summary == "without locator"

        found_with = repo.find_by_locator(task_id, "https://github.com/o/r", "README.md")
        assert found_with is not None
        assert found_with.locator == "README.md"


@pytest.mark.asyncio
async def test_vector_store_chunks_and_query(tmp_path) -> None:
    store = TaskVectorStore("task-vec", persist_dir=str(tmp_path / "chroma"))
    content = {
        "src/main.py": "def main():\n    print('hello world')\n" * 50,
        "README.md": "project readme",
    }
    count = await store.add_chunks(content, source_uri="https://github.com/o/r")
    assert count >= 2

    hits = await store.query("main entrypoint print", n=3)
    assert hits
    assert hits[0]["locator"]
    assert hits[0]["source_uri"] == "https://github.com/o/r"
    assert hits[0]["document"]
