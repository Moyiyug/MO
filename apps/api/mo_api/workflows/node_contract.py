"""统一工作流节点 ID 契约（PRD F-002/F-010）。

PlanStep ID 与 Execute 图节点 ID 的映射，单一真相源。
前端、后端、测试 MUST 使用此文件定义的常量与映射。
"""

from __future__ import annotations

from enum import StrEnum


class WorkflowNode(StrEnum):
    """ExecuteMode 图中所有节点的 ID 常量。"""

    REPO_INGEST = "repo_ingest"
    CODE_UNDERSTANDING = "code_understanding"
    PAPER_RESEARCH = "paper_research"
    REPRODUCIBILITY = "reproducibility"
    SANDBOX_RUNNER = "sandbox_runner"
    COMPARISON_BUILDER = "comparison_builder"
    REPORT_WRITER = "report_writer"


# PlanStep.id → WorkflowNode 映射
PLAN_STEP_TO_NODE: dict[str, WorkflowNode] = {
    "step_repo_ingest": WorkflowNode.REPO_INGEST,
    "step_code_understanding": WorkflowNode.CODE_UNDERSTANDING,
    "step_paper_research": WorkflowNode.PAPER_RESEARCH,
    "step_repro_eval": WorkflowNode.REPRODUCIBILITY,
    "step_comparison": WorkflowNode.COMPARISON_BUILDER,
    "step_sandbox": WorkflowNode.SANDBOX_RUNNER,
    "step_report": WorkflowNode.REPORT_WRITER,
}

# 所有有效的执行图节点 ID（测试用）
EXECUTE_NODE_IDS: set[str] = {n.value for n in WorkflowNode}
