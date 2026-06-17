"""report_writer 节点：轻量占位节点（F-006）。

真正的报告生成在 ExecutionService._complete_task() 中异步后台完成。
本节点仅发布完成事件，结束执行图。
"""

from __future__ import annotations

from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..node_contract import WorkflowNode
from ..state import MOState
from ...models.enums import NodeStatus

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
    return {}
