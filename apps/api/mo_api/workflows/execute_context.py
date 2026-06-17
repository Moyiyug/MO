"""ExecuteMode 运行时上下文注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from ..adapters.model_gateway.gateway import ModelGateway
from ..adapters.paper_research.base import PaperResearchAdapter, WebResearchAdapter
from ..adapters.repo_ingest.base import RepoIngestAdapter
from ..adapters.sandbox.runner import SandboxRunner
from ..models.enums import NodeStatus
from ..models.events import NodeEvent
from ..services.event_bus import EventBus
from ..services.evidence_service import EvidenceService
from ..storage.vector_store import TaskVectorStore
from .state import MOState

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
    sandbox_runner: SandboxRunner


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


async def maybe_skip_node(
    state: MOState,
    node_id: str,
    ctx: ExecuteContext,
) -> bool:
    """检查 node_id 是否在禁用列表中，若禁用则发布 SKIPPED 事件并返回 True。（F-004）"""
    disabled = set(state.get("disabled_node_ids") or [])
    if node_id in disabled:
        await publish_node_event(
            ctx,
            node_id,
            NodeStatus.SKIPPED,
            input_summary="用户在计划中禁用了该步骤",
            logs=[f"{node_id} skipped by approved plan"],
        )
        return True
    return False
