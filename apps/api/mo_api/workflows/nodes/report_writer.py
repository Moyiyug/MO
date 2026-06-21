"""report_writer 节点：轻量占位节点（F-006）。

真正的报告生成在 ExecutionService._complete_task() 中异步后台完成。
本节点仅发布完成事件，结束执行图。
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from ...models.enums import NodeStatus
from ...services.report_seed_service import ReportSeedService
from ...storage import db
from ...storage.repositories import EventRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..node_contract import WorkflowNode
from ..state import MOState

logger = logging.getLogger("mo_api.report_writer")

NODE_ID = WorkflowNode.REPORT_WRITER.value  # "report_writer"


async def report_writer(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="生成最终报告",
        logs=["report_writer started"],
    )
    try:
        with Session(db.get_engine()) as session:
            events = EventRepository(session).list_since(task_id, 0)
            completed = [e.node for e in events if e.status is NodeStatus.COMPLETED]
            failed = [e.node for e in events if e.status is NodeStatus.FAILED]
            evidence_ids = list(
                dict.fromkeys(eid for e in events for eid in (e.evidence_ids or []))
            )
            ReportSeedService(session).upsert_seed(
                task_id=task_id,
                section_key="execution_summary",
                node=NODE_ID,
                narrative_seed=(
                    "执行流程已进入报告撰写阶段。"
                    f"已完成节点：{', '.join(completed[:10]) or '暂无'}。"
                    f"失败节点：{', '.join(failed) or '无'}。"
                ),
                structured_data={
                    "completed_nodes": completed,
                    "failed_nodes": failed,
                    "event_count": len(events),
                },
                evidence_ids=evidence_ids,
                warnings=[f"失败节点：{node}" for node in failed],
            )
    except Exception as exc:
        logger.warning("execution_summary seed write failed: %s", exc)
    return {}
