"""LangGraph 图状态（MO_Backend §6.1）。"""

from __future__ import annotations

from typing import Any, TypedDict


class MOState(TypedDict, total=False):
    task_id: str
    goal: str
    repo_urls: list[str]
    repo_candidates: list[dict[str, Any]]
    paper_urls: list[str]
    output_language: str
    template: str | None
    permissions: dict[str, Any]
    clarification_answers: dict[str, str]
    plan: dict[str, Any]
    pending_approval: dict[str, Any] | None
    errors: list[dict[str, Any]]
    disabled_node_ids: list[str]  # F-004: 用户在计划中禁用的节点 ID
    repo_cards: list[dict[str, Any]]
    evidence_items: list[dict[str, Any]]
    ingested_repos: list[str]
    code_insights: list[dict[str, Any]]
    comparison: dict[str, Any] | None
    paper_materials: list[dict[str, Any]]
    reproducibility: dict[str, Any] | None
    sandbox_completed: bool
