"""ExecuteMode 执行引擎：LangGraph repo_ingest -> code_understanding。"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger("mo_api.execution")

from langgraph.types import Command
from langgraph.errors import GraphInterrupt
from sqlmodel import Session

from ..adapters.model_gateway.gateway import get_model_gateway
from ..adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
from ..adapters.repo_ingest import GitingestAdapter
from ..config import get_settings
from ..models.enums import NodeStatus, TaskStatus
from ..models.events import NodeEvent
from ..models.task import TaskPermissions
from ..services.evidence_service import EvidenceService
from ..services.state_machine import InvalidTransitionError, ensure_transition
from ..services.task_service import TaskNotFoundError
from ..storage.db import get_engine
from ..storage.repositories import TaskRepository
from ..storage.vector_store import TaskVectorStore
from ..workflows.execute_context import (
    ExecuteContext,
    clear_context,
    register_context,
)
from ..workflows.execute_graph import ensure_execute_graph
from ..workflows.state import MOState
from .event_bus import EventBus, get_event_bus


class ExecutionConflictError(Exception):
    """执行状态冲突（如无等待审批的节点）。"""


class ExecutionService:
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._running: set[str] = set()
        self._pending_interrupt: dict[str, str] = {}
        self._start_lock = asyncio.Lock()

    async def start(self, task_id: str) -> TaskStatus:
        async with self._start_lock:
            with Session(get_engine()) as session:
                task_repo = TaskRepository(session)
                task = task_repo.get(task_id)
                if task is None:
                    raise TaskNotFoundError(task_id)

                if task.status is TaskStatus.EXECUTING:
                    status = task.status
                else:
                    if task.status is not TaskStatus.PLAN_APPROVED:
                        raise InvalidTransitionError(
                            f"cannot execute from status {task.status.value}"
                        )
                    ensure_transition(TaskStatus.PLAN_APPROVED, TaskStatus.EXECUTING)
                    updated = task_repo.update_status(task_id, TaskStatus.EXECUTING)
                    assert updated is not None
                    status = updated.status

            if task_id not in self._running:
                self._running.add(task_id)
                asyncio.create_task(self._run(task_id))
            return status

    async def approve_step(
        self, task_id: str, step_id: str, approved: bool
    ) -> None:
        pending = self._pending_interrupt.get(task_id)
        if pending != step_id:
            raise ExecutionConflictError(
                f"step {step_id} is not awaiting approval for task {task_id}"
            )

        if not approved:
            await self._fail_task(task_id, step_id, f"节点 {step_id} 被用户拒绝")
            self._pending_interrupt.pop(task_id, None)
            return

        self._pending_interrupt.pop(task_id, None)
        if task_id not in self._running:
            self._running.add(task_id)
        asyncio.create_task(self._resume(task_id))

    def _build_execute_context(self, task_id: str, session: Session) -> ExecuteContext:
        settings = get_settings()
        chroma_base = settings.chroma_index_dir

        def _vector_factory(tid: str) -> TaskVectorStore:
            return TaskVectorStore(tid, persist_dir=chroma_base)

        return ExecuteContext(
            task_id=task_id,
            event_bus=self.event_bus,
            evidence_service=EvidenceService(session),
            repo_adapter=GitingestAdapter(),
            paper_adapter=PaperQAAdapter(model_gateway=get_model_gateway()),
            web_adapter=GPTResearcherAdapter(),
            model_gateway=get_model_gateway(),
            vector_store_factory=_vector_factory,
        )

    @staticmethod
    def _build_initial_state(session: Session, task_id: str) -> MOState:
        task = TaskRepository(session).get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        permissions = task.permissions.model_dump()
        return {
            "task_id": task_id,
            "goal": task.goal,
            "repo_urls": list(task.repo_urls),
            "paper_urls": list(task.paper_urls),
            "output_language": task.output_language.value,
            "template": task.template,
            "permissions": permissions,
            "repo_cards": [],
            "evidence_items": [],
            "ingested_repos": [],
            "code_insights": [],
            "comparison": None,
            "paper_materials": [],
            "reproducibility": None,
            "errors": [],
        }

    def _graph_config(self, task_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": f"exec:{task_id}"}}

    async def _publish_node(
        self,
        task_id: str,
        node: str,
        status: NodeStatus,
        *,
        input_summary: str | None = None,
        output_summary: str | None = None,
        logs: list[str] | None = None,
        error_message: str | None = None,
        next_action: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> NodeEvent:
        from datetime import datetime, timezone

        event = NodeEvent(
            task_id=task_id,
            seq=0,
            node=node,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            evidence_ids=evidence_ids or [],
            logs=logs or [],
            error_message=error_message,
            next_action=next_action,
            created_at=datetime.now(timezone.utc),
        )
        return await self.event_bus.publish(event)

    async def _fail_task(self, task_id: str, node: str, message: str) -> None:
        await self._publish_node(
            task_id,
            node,
            NodeStatus.FAILED,
            error_message=message,
            logs=[f"node {node} rejected by user"],
        )
        with Session(get_engine()) as session:
            task_repo = TaskRepository(session)
            task = task_repo.get(task_id)
            if task and task.status is not TaskStatus.FAILED:
                task_repo.update_status(task_id, TaskStatus.FAILED)

    async def _complete_task(self, task_id: str) -> None:
        with Session(get_engine()) as session:
            task_repo = TaskRepository(session)
            task = task_repo.get(task_id)
            if task and task.status is TaskStatus.EXECUTING:
                ensure_transition(task.status, TaskStatus.REPORT_DRAFT)
                task_repo.update_status(task_id, TaskStatus.REPORT_DRAFT)
        # 后台预生成报告，不阻塞状态转换（FIX-8）
        asyncio.create_task(self._pregenerate_report(task_id))

    async def _pregenerate_report(self, task_id: str) -> None:
        """后台预生成报告，使首次 GET /report 缓存命中。"""
        try:
            from .report_service import ReportService
            from ..models.enums import TaskStatus as Ts

            with Session(get_engine()) as session:
                task = TaskRepository(session).get(task_id)
                if task is None or task.status not in (
                    Ts.REPORT_DRAFT,
                    Ts.REVIEW_REQUIRED,
                    Ts.DONE,
                ):
                    return
                service = ReportService(session)
                # 仅预热缓存，不推进状态机（GET /report 触发时才推进）
                await service.generate_async(task_id, advance_status=False)
        except Exception as exc:
            logger.warning("report pregenerate failed for task %s: %s", task_id, exc)

    async def _stream_graph(
        self,
        task_id: str,
        graph: Any,
        input_state: Any,
        config: dict[str, Any],
    ) -> None:
        """用 astream 驱动 Execute 图，集中管理节点生命周期事件。

        - 节点启动前发 PENDING（执行层负责）
        - 节点产出后发 COMPLETED（执行层负责）
        - 节点内部发 RUNNING（节点自己负责细粒度进度）
        - GraphInterrupt → WAITING_USER
        - 其它异常 → FAILED（兜底保证）
        """
        snapshot = graph.get_state(config)
        is_resume = bool(snapshot.values) and bool(snapshot.next)

        # ---- 发布初始节点状态 ----
        if is_resume:
            for node in snapshot.next:
                await self._publish_node(
                    task_id,
                    node,
                    NodeStatus.RUNNING,
                    input_summary="继续执行",
                )
        elif snapshot.next:
            for node in snapshot.next:
                await self._publish_node(
                    task_id,
                    node,
                    NodeStatus.PENDING,
                    input_summary="准备执行",
                )
        else:
            # 全新执行——首节点固定为 repo_ingest
            await self._publish_node(
                task_id,
                "repo_ingest",
                NodeStatus.PENDING,
                input_summary="准备执行",
            )

        # ---- astream 驱动图执行 ----
        try:
            async for chunk in graph.astream(
                input_state, config, stream_mode="updates"
            ):
                # 检测 interrupt（stream_mode="updates" 以 chunk 形式返回）
                if "__interrupt__" in chunk:
                    snapshot = graph.get_state(config)
                    if snapshot.next:
                        node = snapshot.next[0]
                        self._pending_interrupt[task_id] = node
                        await self._publish_node(
                            task_id,
                            node,
                            NodeStatus.WAITING_USER,
                            input_summary="等待用户审批",
                            next_action="请审批以继续执行",
                        )
                    return

                for node_name, node_update in chunk.items():
                    # 提取输出摘要与证据 ID 用于 COMPLETED 事件
                    output_summary = None
                    evidence_ids: list[str] = []
                    if isinstance(node_update, dict):
                        repo_cards = node_update.get("repo_cards") or []
                        if repo_cards:
                            output_summary = (
                                f"已摄取 {len(repo_cards)} 个仓库"
                            )
                        evidence_ids = (
                            node_update.get("evidence_ids") or evidence_ids
                        )

                    await self._publish_node(
                        task_id,
                        node_name,
                        NodeStatus.COMPLETED,
                        output_summary=output_summary,
                        evidence_ids=evidence_ids,
                    )

                # 下一个节点 → PENDING
                snapshot = graph.get_state(config)
                if snapshot.next:
                    for node in snapshot.next:
                        await self._publish_node(
                            task_id,
                            node,
                            NodeStatus.PENDING,
                            input_summary="准备执行",
                        )

            # 图正常结束
            await self._complete_task(task_id)

        except GraphInterrupt:
            # ainvoke 模式下的中断（兼容旧调用路径）
            snapshot = graph.get_state(config)
            if snapshot.next:
                node = snapshot.next[0]
                self._pending_interrupt[task_id] = node
                await self._publish_node(
                    task_id,
                    node,
                    NodeStatus.WAITING_USER,
                    input_summary="等待用户审批",
                    next_action="请审批以继续执行",
                )

        except Exception as exc:
            # 兜底：节点异常 → FAILED
            snapshot = graph.get_state(config)
            failed_node = (
                snapshot.next[0] if snapshot.next else "unknown"
            )
            error_msg = str(exc)[:500]
            await self._publish_node(
                task_id,
                failed_node,
                NodeStatus.FAILED,
                error_message=error_msg,
                logs=[f"node {failed_node} failed"],
            )
            await self._fail_task(task_id, failed_node, error_msg)

    async def _run(self, task_id: str) -> None:
        try:
            graph = await ensure_execute_graph()
            config = self._graph_config(task_id)
            with Session(get_engine()) as session:
                register_context(
                    task_id,
                    self._build_execute_context(task_id, session),
                )
                snapshot = graph.get_state(config)
                if not snapshot.values:
                    state = self._build_initial_state(session, task_id)
                else:
                    state = None
                await self._stream_graph(task_id, graph, state, config)
        except Exception as exc:
            logger.exception("_run failed for task %s", task_id)
            await self._fail_task(task_id, "execute_graph", str(exc)[:500])
        finally:
            clear_context(task_id)
            self._running.discard(task_id)

    async def _resume(self, task_id: str) -> None:
        try:
            graph = await ensure_execute_graph()
            config = self._graph_config(task_id)
            with Session(get_engine()) as session:
                register_context(
                    task_id,
                    self._build_execute_context(task_id, session),
                )
                await self._stream_graph(
                    task_id,
                    graph,
                    Command(resume={"approved": True}),
                    config,
                )
        except Exception as exc:
            logger.exception("_resume failed for task %s", task_id)
            await self._fail_task(task_id, "execute_graph", str(exc)[:500])
        finally:
            clear_context(task_id)
            self._running.discard(task_id)


@lru_cache
def get_execution_service() -> ExecutionService:
    return ExecutionService(get_event_bus())


def reset_execution_service_cache() -> None:
    if hasattr(get_execution_service, "cache_clear"):
        get_execution_service.cache_clear()
