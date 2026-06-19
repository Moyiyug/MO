"""任务历史硬删除测试（PRD F-013）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from mo_api.models.task import TaskCreateRequest
from mo_api.services.task_service import TaskService
from mo_api.storage.tables import (
    ComparisonTable,
    EvidenceTable,
    NodeEventTable,
    PlanTable,
    RepoCardTable,
    ReportTable,
    ReproducibilityTable,
    TaskTable,
)


def _count_by_task(session: Session, table_type, task_id: str) -> int:
    return len(
        session.exec(select(table_type).where(table_type.task_id == task_id)).all()
    )


def test_delete_task_removes_associated_storage(
    engine, valid_task_payload, monkeypatch
) -> None:
    cleanup_calls: list[tuple[str, list[str]]] = []

    def fake_cleanup(task_id: str, plan_thread_ids: list[str]) -> None:
        cleanup_calls.append((task_id, plan_thread_ids))

    monkeypatch.setattr(
        "mo_api.services.task_service.cleanup_deleted_task_runtime",
        fake_cleanup,
    )

    with Session(engine) as session:
        service = TaskService(session)
        task = service.create_task(TaskCreateRequest.model_validate(valid_task_payload))
        now = datetime.now(timezone.utc)

        session.add(
            PlanTable(
                id="plan-delete",
                task_id=task.task_id,
                version=1,
                thread_id=f"{task.task_id}:v1",
                plan_data={},
            )
        )
        session.add(
            NodeEventTable(
                id="event-delete",
                task_id=task.task_id,
                seq=1,
                node="plan_builder",
                status="completed",
                payload={},
            )
        )
        session.add(
            EvidenceTable(
                id="ev-delete",
                task_id=task.task_id,
                source_uri="https://github.com/owner/repo-a",
                evidence_data={},
            )
        )
        session.add(
            RepoCardTable(
                id="repo-card-delete",
                task_id=task.task_id,
                repo_url="https://github.com/owner/repo-a",
                card_data={},
            )
        )
        session.add(
            ComparisonTable(
                id="comparison-delete",
                task_id=task.task_id,
                comparison_data={},
                generated_at=now,
            )
        )
        session.add(
            ReproducibilityTable(
                id="repro-delete",
                task_id=task.task_id,
                report_data={},
                generated_at=now,
            )
        )
        session.add(
            ReportTable(
                id="report-delete",
                task_id=task.task_id,
                report_data={},
                generated_at=now,
            )
        )
        session.commit()

        service.delete_task(task.task_id)

        assert session.get(TaskTable, task.task_id) is None
        for table_type in (
            PlanTable,
            NodeEventTable,
            EvidenceTable,
            RepoCardTable,
            ComparisonTable,
            ReproducibilityTable,
            ReportTable,
        ):
            assert _count_by_task(session, table_type, task.task_id) == 0

    assert cleanup_calls == [(task.task_id, [f"{task.task_id}:v1"])]


def test_delete_all_deletable_tasks_skips_executing(
    engine, valid_task_payload, monkeypatch
) -> None:
    cleanup_calls: list[str] = []

    def fake_cleanup(task_id: str, plan_thread_ids: list[str]) -> None:
        cleanup_calls.append(task_id)

    monkeypatch.setattr(
        "mo_api.services.task_service.cleanup_deleted_task_runtime",
        fake_cleanup,
    )

    with Session(engine) as session:
        service = TaskService(session)
        first = service.create_task(TaskCreateRequest.model_validate(valid_task_payload))
        second = service.create_task(TaskCreateRequest.model_validate(valid_task_payload))
        row = session.get(TaskTable, second.task_id)
        assert row is not None
        row.status = "EXECUTING"
        session.add(row)
        session.commit()

        result = service.delete_all_deletable_tasks()

        assert result.deleted_task_ids == [first.task_id]
        assert result.skipped_task_ids == [second.task_id]
        assert session.get(TaskTable, first.task_id) is None
        assert session.get(TaskTable, second.task_id) is not None

    assert cleanup_calls == [first.task_id]
