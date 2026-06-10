"""LangGraph 图状态（MO_Backend §6.1）。"""

from __future__ import annotations

from typing import Any, TypedDict


class MOState(TypedDict, total=False):
    task_id: str
    goal: str
    repo_urls: list[str]
    paper_urls: list[str]
    output_language: str
    template: str | None
    permissions: dict[str, Any]
    clarification_answers: dict[str, str]
    plan: dict[str, Any]
    pending_approval: dict[str, Any] | None
    errors: list[dict[str, Any]]
