"""ReportSectionSeed Repository 单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import TaskStatus
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.services.report_seed_service import ReportSeedService
from mo_api.storage.repositories import ReportSectionSeedRepository, TaskRepository
from mo_api.storage.tables import TaskTable


def _seed(
    *,
    seed_id: str = "s1",
    task_id: str = "t1",
    section_key: str = "repo_overview",
    node: str = "repo_ingest",
    text: str = "seed",
    created_at: datetime | None = None,
) -> ReportSectionSeed:
    now = created_at or datetime.now(timezone.utc)
    return ReportSectionSeed(
        id=seed_id,
        task_id=task_id,
        section_key=section_key,
        node=node,
        title="仓库概览",
        narrative_seed=text,
        structured_data={"a": 1},
        evidence_ids=["e1"],
        warnings=[],
        created_at=now,
        updated_at=now,
    )


def test_report_seed_upsert_is_idempotent(engine) -> None:
    with Session(engine) as session:
        repo = ReportSectionSeedRepository(session)
        first = repo.upsert(_seed(seed_id="s1", text="first"))
        second = repo.upsert(_seed(seed_id="s2", text="second"))
        items = repo.list_by_task("t1")

    assert len(items) == 1
    assert items[0].id == "s1"
    assert items[0].narrative_seed == "second"
    assert first.id == second.id


def test_report_seed_list_by_task_orders_by_created_at(engine) -> None:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(engine) as session:
        repo = ReportSectionSeedRepository(session)
        repo.upsert(
            _seed(
                seed_id="late",
                section_key="risks",
                node="critic_review",
                created_at=base + timedelta(minutes=2),
            )
        )
        repo.upsert(
            _seed(
                seed_id="early",
                section_key="repo_overview",
                node="repo_ingest",
                created_at=base,
            )
        )
        items = repo.list_by_task("t1")

    assert [item.id for item in items] == ["early", "late"]


def test_report_seed_list_by_task_and_section_filters_section(engine) -> None:
    with Session(engine) as session:
        repo = ReportSectionSeedRepository(session)
        repo.upsert(_seed(section_key="repo_overview", node="repo_ingest"))
        repo.upsert(_seed(seed_id="s2", section_key="risks", node="critic_review"))
        items = repo.list_by_task_and_section("t1", "repo_overview")

    assert len(items) == 1
    assert items[0].section_key == "repo_overview"


def test_report_seed_delete_by_task_removes_all_task_seeds(engine) -> None:
    with Session(engine) as session:
        repo = ReportSectionSeedRepository(session)
        repo.upsert(_seed(task_id="t1", section_key="repo_overview"))
        repo.upsert(_seed(seed_id="s2", task_id="t1", section_key="risks", node="critic_review"))
        repo.upsert(_seed(seed_id="s3", task_id="t2", section_key="repo_overview"))
        repo.delete_by_task("t1")
        remaining_t1 = repo.list_by_task("t1")
        remaining_t2 = repo.list_by_task("t2")

    assert remaining_t1 == []
    assert len(remaining_t2) == 1


def test_task_delete_bundle_removes_report_section_seeds(engine) -> None:
    with Session(engine) as session:
        session.add(
            TaskTable(
                id="t1",
                goal="测试目标",
                repo_urls=[],
                paper_urls=[],
                output_language="zh",
                template=None,
                permissions={"allow_repo_clone": True},
                status=TaskStatus.REPORT_DRAFT.value,
            )
        )
        session.commit()

        seed_repo = ReportSectionSeedRepository(session)
        seed_repo.upsert(_seed(task_id="t1"))
        assert len(seed_repo.list_by_task("t1")) == 1

        deleted_threads = TaskRepository(session).delete_bundle("t1")
        remaining = seed_repo.list_by_task("t1")

    assert deleted_threads == []
    assert remaining == []


def test_report_seed_service_validates_section_and_deduplicates(engine) -> None:
    with Session(engine) as session:
        service = ReportSeedService(session)
        saved = service.upsert_seed(
            task_id="t1",
            section_key="repo_overview",
            node="repo_ingest",
            narrative_seed="  " + ("x" * 9000),
            structured_data={"repo": "demo"},
            evidence_ids=["e1", "e1", "e2"],
            warnings=["w1", "w1"],
        )

        with pytest.raises(ValueError, match="unknown report section key"):
            service.upsert_seed(
                task_id="t1",
                section_key="unknown",
                node="repo_ingest",
                narrative_seed="seed",
            )

    assert len(saved.narrative_seed) == 8000
    assert saved.evidence_ids == ["e1", "e2"]
    assert saved.warnings == ["w1"]
