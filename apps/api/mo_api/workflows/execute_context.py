"""ExecuteMode 运行时上下文注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..adapters.model_gateway.gateway import ModelGateway
from ..adapters.paper_research.base import PaperResearchAdapter, WebResearchAdapter
from ..adapters.repo_ingest.base import RepoIngestAdapter
from ..models.enums import NodeStatus
from ..models.events import NodeEvent
from ..services.event_bus import EventBus
from ..services.evidence_service import EvidenceService
from ..storage.vector_store import TaskVectorStore

_registry: dict[str, ExecuteContext] = {}


@dataclass
class ExecuteContext:
    task_id: str
    event_bus: EventBus
    evidence_service: EvidenceService
    repo_adapter: RepoIngestAdapter
    paper_adapter: PaperResearchAdapter
    web_adapter: WebResearchAdapter
    model_gateway: ModelGateway
    vector_store_factory: Callable[[str], TaskVectorStore]


def register_context(task_id: str, ctx: ExecuteContext) -> None:
    _registry[task_id] = ctx


def get_context(task_id: str) -> ExecuteContext:
    ctx = _registry.get(task_id)
    if ctx is None:
        raise KeyError(f"execute context not registered for task {task_id}")
    return ctx


def clear_context(task_id: str) -> None:
    _registry.pop(task_id, None)


async def publish_node_event(
    ctx: ExecuteContext,
    node: str,
    status: NodeStatus,
    **kwargs,
) -> NodeEvent:
    event = NodeEvent(
        task_id=ctx.task_id,
        seq=0,
        node=node,
        status=status,
        created_at=datetime.now(timezone.utc),
        **kwargs,
    )
    return await ctx.event_bus.publish(event)
