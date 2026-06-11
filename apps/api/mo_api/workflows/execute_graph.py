"""ExecuteMode LangGraph：repo_ingest -> code_understanding -> paper_research -> reproducibility -> comparison_builder。"""

from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from .nodes.code_understanding import code_understanding
from .nodes.comparison_builder import comparison_builder
from .nodes.paper_research import paper_research
from .nodes.reproducibility import reproducibility
from .nodes.repo_ingest import repo_ingest
from .state import MOState

_execute_graph: Any | None = None
_init_lock = asyncio.Lock()


def build_execute_graph(checkpointer: Any) -> Any:
    graph = StateGraph(MOState)
    graph.add_node("repo_ingest", repo_ingest)
    graph.add_node("code_understanding", code_understanding)
    graph.add_node("paper_research", paper_research)
    graph.add_node("reproducibility", reproducibility)
    graph.add_node("comparison_builder", comparison_builder)
    graph.add_edge(START, "repo_ingest")
    graph.add_edge("repo_ingest", "code_understanding")
    graph.add_edge("code_understanding", "paper_research")
    graph.add_edge("paper_research", "reproducibility")
    graph.add_edge("reproducibility", "comparison_builder")
    graph.add_edge("comparison_builder", END)
    return graph.compile(checkpointer=checkpointer)


async def ensure_execute_graph() -> Any:
    """懒加载 ExecuteGraph（AsyncSqliteSaver + astream）。

    使用双重检查锁防止并发初始化。"""
    global _execute_graph
    if _execute_graph is not None:
        return _execute_graph

    async with _init_lock:
        if _execute_graph is not None:
            return _execute_graph

        settings = get_settings()
        db_path = settings.execute_checkpoint_db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        conn_string = (
            db_path
            if db_path.startswith("sqlite")
            else f"sqlite+aiosqlite:///{db_path}"
        )
        checkpointer = AsyncSqliteSaver.from_conn_string(conn_string)
        await checkpointer.setup()
        _execute_graph = build_execute_graph(checkpointer)
        return _execute_graph


@lru_cache
def get_execute_graph() -> Any:
    """同步访问已初始化的 graph（测试 fixture 注入后使用）。"""
    if _execute_graph is None:
        raise RuntimeError("execute graph not initialized; call ensure_execute_graph() first")
    return _execute_graph


def set_execute_graph(graph: Any) -> None:
    """测试用：注入预编译 graph。"""
    global _execute_graph
    _execute_graph = graph
    if hasattr(get_execute_graph, "cache_clear"):
        get_execute_graph.cache_clear()


def reset_execute_graph_cache() -> None:
    global _execute_graph
    _execute_graph = None
    if hasattr(get_execute_graph, "cache_clear"):
        get_execute_graph.cache_clear()
