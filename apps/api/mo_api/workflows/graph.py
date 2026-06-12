"""PlanMode LangGraph：task_intake -> plan_builder -> approval_gate(interrupt)。"""

from __future__ import annotations

import os
import sqlite3
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..config import get_settings
from .nodes.plan_builder import plan_builder
from .nodes.repo_discovery import repo_discovery
from .nodes.task_intake import task_intake
from .state import MOState

_checkpoint_conn: sqlite3.Connection | None = None


def approval_gate(state: MOState) -> MOState:
    """在任意执行副作用前 interrupt，等待用户批准计划（R-001 / R-004）。"""
    plan = state.get("plan") or {}
    decision = interrupt(
        {
            "action": "approve_plan",
            "requires_approval": True,
            "plan_id": plan.get("id"),
            "task_id": state.get("task_id"),
        }
    )
    return {
        "pending_approval": None if decision.get("approved") else decision,
    }


def build_plan_graph(checkpointer: SqliteSaver) -> Any:
    graph = StateGraph(MOState)
    graph.add_node("task_intake", task_intake)
    graph.add_node("repo_discovery", repo_discovery)
    graph.add_node("plan_builder", plan_builder)
    graph.add_node("approval_gate", approval_gate)
    graph.add_edge(START, "task_intake")
    graph.add_edge("task_intake", "repo_discovery")
    graph.add_edge("repo_discovery", "plan_builder")
    graph.add_edge("plan_builder", "approval_gate")
    graph.add_edge("approval_gate", END)
    return graph.compile(checkpointer=checkpointer)


def _get_checkpoint_conn() -> sqlite3.Connection:
    global _checkpoint_conn
    if _checkpoint_conn is None:
        settings = get_settings()
        db_path = settings.checkpoint_db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        _checkpoint_conn = sqlite3.connect(db_path, check_same_thread=False)
        saver = SqliteSaver(_checkpoint_conn)
        saver.setup()
    return _checkpoint_conn


@lru_cache
def get_plan_graph() -> Any:
    conn = _get_checkpoint_conn()
    saver = SqliteSaver(conn)
    return build_plan_graph(saver)


def reset_plan_graph_cache() -> None:
    """测试用：清除 graph 缓存。"""
    if hasattr(get_plan_graph, "cache_clear"):
        get_plan_graph.cache_clear()
