"""task_intake 节点：归一化任务输入到图状态。"""

from __future__ import annotations

from ..state import MOState


def task_intake(state: MOState) -> MOState:
    return {
        "task_id": state.get("task_id", ""),
        "goal": state.get("goal", ""),
        "repo_urls": list(state.get("repo_urls") or []),
        "paper_urls": list(state.get("paper_urls") or []),
        "output_language": state.get("output_language", "zh"),
        "template": state.get("template"),
        "permissions": dict(state.get("permissions") or {}),
        "clarification_answers": dict(state.get("clarification_answers") or {}),
        "errors": list(state.get("errors") or []),
    }
