"""ExecutionService 单元测试。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import NodeStatus, TaskStatus
from mo_api.models.repo import RepoDigest
from mo_api.services.event_bus import EventBus
from mo_api.services.execution_service import ExecutionService
from mo_api.storage.repositories import EventRepository, TaskRepository
from mo_api.storage.tables import TaskTable


class _FakeProfile:
    id = "fake"


@pytest.fixture
def mock_repo_ingest(monkeypatch):
    async def fake_ingest(self, repo_url: str, *, token: str | None = None):
        return RepoDigest(
            summary="summary",
            tree="README.md",
            content={
                "README.md": "# demo",
                "requirements.txt": "requests>=2.0",
            },
            source_uri=repo_url,
        )

    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.GitingestAdapter.ingest",
        fake_ingest,
    )


@pytest.fixture
def mock_gateway(monkeypatch):
    async def fake_complete(self, profile, messages, **kwargs):
        if "core_modules" in messages[0]["content"]:
            return '{"core_modules":["main.py"], "execution_path":"main -> run"}'
        return '{"project_type":"library","entrypoints":["main.py"],"risks":[]}'

    def fake_select(self, **kwargs):
        return _FakeProfile()

    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.ModelGateway.complete",
        fake_complete,
    )
    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.ModelGateway.select",
        fake_select,
    )


@pytest.fixture
def event_bus(engine, monkeypatch):
    monkeypatch.setattr("mo_api.services.event_bus.get_engine", lambda: engine)
    monkeypatch.setattr("mo_api.services.execution_service.get_engine", lambda: engine)
    return EventBus()


@pytest.fixture
def executor(event_bus):
    return ExecutionService(event_bus)


def _seed_task(
    engine,
    task_id: str,
    *,
    status: TaskStatus = TaskStatus.PLAN_APPROVED,
    allow_repo_clone: bool = True,
) -> None:
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="理解仓库",
                repo_urls=["https://github.com/o/r"],
                paper_urls=[],
                status=status.value,
                permissions={"allow_repo_clone": allow_repo_clone},
            )
        )
        session.commit()


async def _wait_for_task_status(
    engine, task_id: str, expected: TaskStatus, *, timeout: float = 5.0
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            task = TaskRepository(session).get(task_id)
            if task is not None and task.status is expected:
                return
        await asyncio.sleep(0.1)
    with Session(engine) as session:
        task = TaskRepository(session).get(task_id)
    assert task is not None
    assert task.status is expected


@pytest.mark.asyncio
async def test_execute_emits_pending_running_completed(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-1"
    _seed_task(engine, task_id, allow_repo_clone=True)

    await executor.start(task_id)
    await _wait_for_task_status(engine, task_id, TaskStatus.REPORT_DRAFT)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        statuses = [e.status for e in events]
        assert NodeStatus.PENDING in statuses
        assert NodeStatus.RUNNING in statuses
        assert NodeStatus.COMPLETED in statuses
        nodes = {e.node for e in events}
        assert "repo_ingest" in nodes
        assert "code_understanding" in nodes
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.REPORT_DRAFT


@pytest.mark.asyncio
async def test_requires_approval_pauses_at_waiting_user(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-2"
    _seed_task(engine, task_id, allow_repo_clone=False)

    await executor.start(task_id)
    await asyncio.sleep(0.3)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(
            e.node == "repo_ingest" and e.status is NodeStatus.WAITING_USER for e in events
        )
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.EXECUTING


@pytest.mark.asyncio
async def test_approve_step_resumes_to_completed(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-3"
    _seed_task(engine, task_id, allow_repo_clone=False)

    await executor.start(task_id)
    await asyncio.sleep(0.3)
    await executor.approve_step(task_id, "repo_ingest", True)
    await _wait_for_task_status(engine, task_id, TaskStatus.REPORT_DRAFT)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(
            e.node == "code_understanding" and e.status is NodeStatus.COMPLETED
            for e in events
        )
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.REPORT_DRAFT


@pytest.mark.asyncio
async def test_reject_step_fails_task(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-4"
    _seed_task(engine, task_id, allow_repo_clone=False)

    await executor.start(task_id)
    await asyncio.sleep(0.3)
    await executor.approve_step(task_id, "repo_ingest", False)
    await asyncio.sleep(0.2)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(e.status is NodeStatus.FAILED for e in events)
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.FAILED


@pytest.mark.asyncio
async def test_start_idempotent_when_already_running(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-6"
    _seed_task(engine, task_id, allow_repo_clone=False)

    await executor.start(task_id)
    executor._running.add(task_id)
    status = await executor.start(task_id)
    assert status is TaskStatus.EXECUTING


@pytest.mark.asyncio
async def test_start_recovers_stale_executing_task(
    engine, executor, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-stale"
    _seed_task(engine, task_id, status=TaskStatus.EXECUTING, allow_repo_clone=True)

    status = await executor.start(task_id)
    assert status is TaskStatus.EXECUTING
    await _wait_for_task_status(engine, task_id, TaskStatus.REPORT_DRAFT)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(e.status is NodeStatus.COMPLETED for e in events)
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.REPORT_DRAFT


@pytest.mark.asyncio
async def test_waiting_user_can_be_approved_when_event_is_published(
    engine, mock_repo_ingest, mock_gateway
) -> None:
    task_id = "exec-race"
    _seed_task(engine, task_id, allow_repo_clone=False)

    class AutoApprovingBus(EventBus):
        executor: ExecutionService

        async def publish(self, event):
            saved = await super().publish(event)
            if saved.status is NodeStatus.WAITING_USER:
                await self.executor.approve_step(saved.task_id, saved.node, True)
            return saved

    bus = AutoApprovingBus()
    executor = ExecutionService(bus)
    bus.executor = executor

    await executor.start(task_id)
    await _wait_for_task_status(engine, task_id, TaskStatus.REPORT_DRAFT)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
        assert any(
            e.node == "code_understanding" and e.status is NodeStatus.COMPLETED
            for e in events
        )
        task = TaskRepository(session).get(task_id)
        assert task is not None
        assert task.status is TaskStatus.REPORT_DRAFT
