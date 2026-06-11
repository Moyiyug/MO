"""进程内事件总线：持久化 + 内存 pub/sub（M4）。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from functools import lru_cache

from sqlmodel import Session

from ..models.events import NodeEvent
from ..storage.db import get_engine
from ..storage.repositories import EventRepository


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[NodeEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    def subscribe(self, task_id: str) -> asyncio.Queue[NodeEvent]:
        queue: asyncio.Queue[NodeEvent] = asyncio.Queue()
        self._subscribers[task_id].add(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[NodeEvent]) -> None:
        self._subscribers[task_id].discard(queue)
        if not self._subscribers[task_id]:
            del self._subscribers[task_id]

    def list_since(self, task_id: str, since_seq: int) -> list[NodeEvent]:
        with Session(get_engine()) as session:
            return EventRepository(session).list_since(task_id, since_seq)

    async def publish(self, event: NodeEvent) -> NodeEvent:
        async with self._lock:
            with Session(get_engine()) as session:
                saved = EventRepository(session).append(event)
            for queue in list(self._subscribers.get(event.task_id, set())):
                await queue.put(saved)
        return saved


@lru_cache
def get_event_bus() -> EventBus:
    return EventBus()


def reset_event_bus_cache() -> None:
    if hasattr(get_event_bus, "cache_clear"):
        get_event_bus.cache_clear()
