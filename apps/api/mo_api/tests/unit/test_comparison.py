"""多仓库对比单元/集成测试（PRD F-008）。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session

from mo_api.models.comparison import (
    COMPARISON_DIMENSIONS,
    ComparisonMatrix,
    DimensionScore,
    RepoRanking,
)
from mo_api.models.enums import ClaimLabel, TaskStatus
from mo_api.models.plan import DEFAULT_RUBRIC_WEIGHTS, Plan, ReportRubric
from mo_api.models.repo import RepoCard
from mo_api.services.comparison_service import (
    build_recommendation,
    compute_rankings,
    recompute_matrix,
)
from mo_api.workflows.nodes.comparison_builder import (
    _fallback_dimension_score,
    _needs_score_fallback,
)
from mo_api.storage.repositories import ComparisonRepository, PlanRepository
from mo_api.storage.tables import TaskTable


def _make_repo_card(task_id: str, url: str, name: str) -> RepoCard:
    return RepoCard(
        id=uuid.uuid4().hex,
        task_id=task_id,
        repo_url=url,
        repo_name=name,
        summary="demo",
        primary_language="Python",
        project_type="library",
        entrypoints=["main.py"],
        test_commands=["pytest"],
        docs_paths=["README.md"],
        license="MIT",
        risks=["low coverage"],
        evidence_ids=[],
    )


def test_compute_rankings_weighted_total() -> None:
    cards = [
        _make_repo_card("t1", "https://github.com/o/a", "repo-a"),
        _make_repo_card("t1", "https://github.com/o/b", "repo-b"),
    ]
    scores = [
        DimensionScore(
            dimension="reproducibility",
            repo_url=cards[0].repo_url,
            score=0.9,
            rationale="good",
            evidence_ids=["e1"],
        ),
        DimensionScore(
            dimension="reproducibility",
            repo_url=cards[1].repo_url,
            score=0.5,
            rationale="ok",
            evidence_ids=["e2"],
        ),
        DimensionScore(
            dimension="documentation",
            repo_url=cards[0].repo_url,
            score=0.8,
            rationale="docs",
            evidence_ids=["e3"],
        ),
        DimensionScore(
            dimension="documentation",
            repo_url=cards[1].repo_url,
            score=0.7,
            rationale="docs",
            evidence_ids=["e4"],
        ),
    ]
    weights = dict(DEFAULT_RUBRIC_WEIGHTS)
    rankings = compute_rankings(scores, cards, weights)
    assert len(rankings) == 2
    assert rankings[0].weighted_total >= rankings[1].weighted_total


def test_build_recommendation_has_limitations_and_evidence() -> None:
    cards = [
        _make_repo_card("t1", "https://github.com/o/a", "repo-a"),
        _make_repo_card("t1", "https://github.com/o/b", "repo-b"),
    ]
    scores = [
        DimensionScore(
            dimension="reproducibility",
            repo_url=cards[0].repo_url,
            score=0.9,
            rationale="good",
            evidence_ids=["ev-a"],
        ),
        DimensionScore(
            dimension="reproducibility",
            repo_url=cards[1].repo_url,
            score=0.4,
            rationale="weak",
            evidence_ids=["ev-b"],
        ),
    ]
    rankings = [
        RepoRanking(
            repo_url=cards[0].repo_url,
            repo_name="repo-a",
            weighted_total=0.85,
            per_dimension={"reproducibility": 0.9},
        ),
        RepoRanking(
            repo_url=cards[1].repo_url,
            repo_name="repo-b",
            weighted_total=0.4,
            per_dimension={"reproducibility": 0.4},
        ),
    ]
    rec, limitations, evidence_ids = build_recommendation(rankings, scores, cards)
    assert "repo-a" in rec
    assert len(limitations) >= 1
    assert "ev-a" in evidence_ids


def test_recompute_matrix_changes_total_without_new_scores() -> None:
    cards = [
        _make_repo_card("t1", "https://github.com/o/a", "repo-a"),
        _make_repo_card("t1", "https://github.com/o/b", "repo-b"),
    ]
    scores: list[DimensionScore] = []
    for dim in ("reproducibility", "documentation", "research_value", "engineering_fit", "extensibility"):
        scores.append(
            DimensionScore(
                dimension=dim,
                repo_url=cards[0].repo_url,
                score=0.8,
                rationale="a",
                evidence_ids=["e1"],
            )
        )
        scores.append(
            DimensionScore(
                dimension=dim,
                repo_url=cards[1].repo_url,
                score=0.6,
                rationale="b",
                evidence_ids=["e2"],
            )
        )

    matrix = ComparisonMatrix(
        id=uuid.uuid4().hex,
        task_id="t1",
        repo_urls=[c.repo_url for c in cards],
        scores=scores,
        rankings=compute_rankings(scores, cards, dict(DEFAULT_RUBRIC_WEIGHTS)),
        generated_at=datetime.now(timezone.utc),
    )
    original_total = matrix.rankings[0].weighted_total

    new_weights = {
        "reproducibility": 0.10,
        "documentation": 0.10,
        "research_value": 0.10,
        "engineering_fit": 0.10,
        "extensibility": 0.60,
    }
    updated = recompute_matrix(matrix, new_weights, cards)
    assert updated.weights == new_weights
    assert len(updated.scores) == len(scores)
    assert updated.rankings[0].weighted_total != original_total or new_weights != dict(
        DEFAULT_RUBRIC_WEIGHTS
    )


@pytest.mark.asyncio
async def test_comparison_builder_via_execute(client, engine) -> None:
    """2 仓库执行后生成对比矩阵（mock LLM）。"""
    from mo_api.tests.integration.test_report_generation import (
        _approve_all_waiting_steps,
        _approve_plan_flow,
        _wait_for_report_draft,
    )

    payload = {
        "goal": "对比两个 RAG 框架",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]

    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)

    comp_resp = await client.get(f"/api/tasks/{task_id}/comparison")
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert len(data["repo_urls"]) == 2
    assert len(data["dimensions"]) == len(COMPARISON_DIMENSIONS)
    assert len(data["rankings"]) == 2
    assert data["recommendation"]
    assert len(data["limitations"]) >= 1
    assert data["recommendation_evidence_ids"]


@pytest.mark.asyncio
async def test_recompute_endpoint(client, engine) -> None:
    from mo_api.tests.integration.test_report_generation import (
        _approve_all_waiting_steps,
        _approve_plan_flow,
        _wait_for_report_draft,
    )

    payload = {
        "goal": "对比",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]
    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)

    before = (await client.get(f"/api/tasks/{task_id}/comparison")).json()
    old_total = before["rankings"][0]["weighted_total"]

    new_weights = {
        "reproducibility": 0.10,
        "documentation": 0.10,
        "research_value": 0.10,
        "engineering_fit": 0.10,
        "extensibility": 0.60,
    }
    resp = await client.post(
        f"/api/tasks/{task_id}/comparison",
        json={"weights": new_weights},
    )
    assert resp.status_code == 200
    after = resp.json()
    assert after["weights"] == new_weights
    assert len(after["scores"]) == len(before["scores"])


@pytest.mark.asyncio
async def test_comparison_skipped_single_repo(client, engine) -> None:
    from mo_api.models.enums import NodeStatus
    from mo_api.storage.repositories import EventRepository
    from mo_api.tests.integration.test_report_generation import (
        _approve_all_waiting_steps,
        _approve_plan_flow,
        _wait_for_report_draft,
    )

    payload = {
        "goal": "单仓库",
        "repo_urls": ["https://github.com/owner/repo-a"],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]
    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)

    with Session(engine) as session:
        events = EventRepository(session).list_since(task_id, 0)
    cb_events = [e for e in events if e.node == "comparison_builder"]
    assert any(e.status is NodeStatus.SKIPPED for e in cb_events)

    comp = await client.get(f"/api/tasks/{task_id}/comparison")
    assert comp.status_code == 404


def test_dimension_score_claim_label() -> None:
    ds = DimensionScore(
        dimension="documentation",
        repo_url="https://github.com/o/r",
        score=0.5,
        rationale="",
        evidence_ids=[],
        label=ClaimLabel.PENDING,
    )
    assert ds.label is ClaimLabel.PENDING


def test_comparison_fallback_scores_from_repo_card_signals() -> None:
    card = _make_repo_card("t1", "https://github.com/o/a", "repo-a")
    score, rationale = _fallback_dimension_score(card, "reproducibility")
    assert 0.0 < score <= 1.0
    assert "RepoCard" in rationale
    assert "project_type=" not in rationale
    assert _needs_score_fallback(0.5, "评分依据不足") is True
    assert _needs_score_fallback(0.2, '{"score": 0.2,') is True
    assert _needs_score_fallback(score, rationale) is False


@pytest.mark.asyncio
async def test_recompute_invalid_weights_rejected(client, engine) -> None:
    """sum(weights) != 1.0 应返回 422。"""
    from mo_api.tests.integration.test_report_generation import (
        _approve_all_waiting_steps,
        _approve_plan_flow,
        _wait_for_report_draft,
    )

    payload = {
        "goal": "对比",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]
    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)

    resp = await client.post(
        f"/api/tasks/{task_id}/comparison",
        json={"weights": {"reproducibility": 0.5}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recompute_without_comparison_returns_404(client, engine) -> None:
    """执行后手动清除对比数据，POST /comparison 应返回 404。"""
    from mo_api.tests.integration.test_report_generation import (
        _approve_all_waiting_steps,
        _approve_plan_flow,
        _wait_for_report_draft,
    )

    payload = {
        "goal": "对比",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]
    await _approve_plan_flow(client, task_id)
    await client.post(f"/api/tasks/{task_id}/execute")
    await _approve_all_waiting_steps(client, task_id, engine)
    await _wait_for_report_draft(client, task_id)

    # 手动清除对比数据
    from mo_api.storage.repositories import ComparisonRepository
    from sqlmodel import Session
    with Session(engine) as session:
        ComparisonRepository(session).delete_by_task(task_id)

    resp = await client.post(
        f"/api/tasks/{task_id}/comparison",
        json={
            "weights": {
                "reproducibility": 0.2,
                "documentation": 0.2,
                "research_value": 0.2,
                "engineering_fit": 0.2,
                "extensibility": 0.2,
            },
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recompute_rejected_for_wrong_status(client, engine) -> None:
    """PLAN_APPROVED 状态不允许重算，应返回 409。"""
    payload = {
        "goal": "对比",
        "repo_urls": [
            "https://github.com/owner/repo-a",
            "https://github.com/owner/repo-b",
        ],
        "permissions": {"allow_repo_clone": True},
    }
    create = await client.post("/api/tasks", json=payload)
    task_id = create.json()["task_id"]
    # 仅推进到 PLAN_APPROVED 但不执行
    await client.post(f"/api/tasks/{task_id}/plan")
    await client.post(
        f"/api/tasks/{task_id}/clarifications",
        json={"answers": [{"question_id": "comparison_focus", "answer": "可复现性"}]},
    )
    await client.post(f"/api/tasks/{task_id}/approve-plan", json={})

    resp = await client.post(
        f"/api/tasks/{task_id}/comparison",
        json={
            "weights": {
                "reproducibility": 0.2,
                "documentation": 0.2,
                "research_value": 0.2,
                "engineering_fit": 0.2,
                "extensibility": 0.2,
            },
        },
    )
    assert resp.status_code == 409
