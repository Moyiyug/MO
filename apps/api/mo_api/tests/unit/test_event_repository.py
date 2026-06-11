"""EventRepository 单元测试。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.enums import NodeStatus
from mo_api.models.events import NodeEvent
from mo_api.storage.repositories import EventRepository
from mo_api.storage.tables import NodeEventTable


def _event(task_id: str, node: str, status: NodeStatus, seq: int = 0) -> NodeEvent:
    return NodeEvent(
        task_id=task_id,
        seq=seq,
        node=node,
        status=status,
        created_at=datetime.now(timezone.utc),
    )


def test_append_assigns_monotonic_seq(engine) -> None:
    task_id = "task-1"
    with Session(engine) as session:
        repo = EventRepository(session)
        e1 = repo.append(_event(task_id, "step_a", NodeStatus.PENDING))
        e2 = repo.append(_event(task_id, "step_a", NodeStatus.RUNNING))
        assert e1.seq == 1
        assert e2.seq == 2
        assert repo.max_seq(task_id) == 2


def test_list_since_returns_ordered_events(engine) -> None:
    task_id = "task-2"
    with Session(engine) as session:
        repo = EventRepository(session)
        repo.append(_event(task_id, "s1", NodeStatus.PENDING))
        repo.append(_event(task_id, "s1", NodeStatus.RUNNING))
        repo.append(_event(task_id, "s1", NodeStatus.COMPLETED))

    with Session(engine) as session:
        repo = EventRepository(session)
        events = repo.list_since(task_id, 1)
        assert len(events) == 2
        assert events[0].seq == 2
        assert events[1].seq == 3
        assert events[0].status is NodeStatus.RUNNING


def test_max_seq_empty_returns_zero(engine) -> None:
    with Session(engine) as session:
        assert EventRepository(session).max_seq("missing") == 0


def test_node_event_task_seq_unique_constraint_exists() -> None:
    constraints = {
        constraint.name
        for constraint in NodeEventTable.__table__.constraints
        if constraint.name
    }
    assert "uq_node_events_task_seq" in constraints
