"""多仓库对比服务（PRD F-008）。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from ..models.comparison import (
    COMPARISON_DIMENSIONS,
    WEIGHTED_DIMENSIONS,
    ComparisonMatrix,
    DimensionScore,
    RepoRanking,
)
from ..models.plan import DEFAULT_RUBRIC_WEIGHTS
from ..models.repo import RepoCard
from ..storage.repositories import ComparisonRepository


def compute_rankings(
    scores: list[DimensionScore],
    repo_cards: list[RepoCard],
    weights: dict[str, float],
) -> list[RepoRanking]:
    """按 rubric 权重计算各仓库加权总分并排名。"""
    by_repo: dict[str, dict[str, float]] = {}
    for ds in scores:
        by_repo.setdefault(ds.repo_url, {})[ds.dimension] = ds.score

    name_map = {c.repo_url: c.repo_name for c in repo_cards}
    rankings: list[RepoRanking] = []

    for repo_url, dims in by_repo.items():
        total = 0.0
        used_weight = 0.0
        for wdim, w in weights.items():
            if wdim in dims:
                total += dims[wdim] * w
                used_weight += w
        if used_weight > 0:
            total = total / used_weight
        rankings.append(
            RepoRanking(
                repo_url=repo_url,
                repo_name=name_map.get(repo_url, repo_url),
                weighted_total=round(total, 4),
                per_dimension=dict(dims),
            )
        )

    rankings.sort(key=lambda r: r.weighted_total, reverse=True)
    return rankings


def build_recommendation(
    rankings: list[RepoRanking],
    scores: list[DimensionScore],
    repo_cards: list[RepoCard],
) -> tuple[str, list[str], list[str]]:
    """生成场景推荐、局限说明与关联 evidence_ids。"""
    if not rankings:
        return "暂无足够数据进行推荐", ["对比仓库不足"], []

    top = rankings[0]
    runner_up = rankings[1] if len(rankings) > 1 else None

    evidence_ids: list[str] = []
    for ds in scores:
        if ds.repo_url == top.repo_url:
            evidence_ids.extend(ds.evidence_ids)

    recommendation = (
        f"综合加权得分，推荐优先考虑 **{top.repo_name}**（{top.repo_url}），"
        f"加权总分 {top.weighted_total:.2f}。"
    )
    if runner_up:
        recommendation += (
            f" 若更关注特定维度，可参考 **{runner_up.repo_name}**"
            f"（总分 {runner_up.weighted_total:.2f}）。"
        )

    limitations: list[str] = []
    top_card = next((c for c in repo_cards if c.repo_url == top.repo_url), None)
    if top_card and top_card.risks:
        limitations.extend(f"{top.repo_name}: {r}" for r in top_card.risks[:3])

    for ds in scores:
        if ds.score < 0.4:
            limitations.append(
                f"{ds.repo_url} 在 {ds.dimension} 维度得分较低（{ds.score:.2f}）"
            )

    if runner_up:
        gap = top.weighted_total - runner_up.weighted_total
        if gap < 0.05:
            limitations.append(
                f"前两名仓库得分接近（差距 {gap:.2f}），推荐置信度有限，建议结合场景细评"
            )

    limitations.append("对比基于 RepoCard 与代码理解推断，未包含复现实测（M9）")

    return recommendation, limitations[:8], list(dict.fromkeys(evidence_ids))


def recompute_matrix(
    matrix: ComparisonMatrix,
    new_weights: dict[str, float],
    repo_cards: list[RepoCard],
) -> ComparisonMatrix:
    """用新权重对已存分数重新加权，不重跑 LLM。"""
    rankings = compute_rankings(matrix.scores, repo_cards, new_weights)
    recommendation, limitations, evidence_ids = build_recommendation(
        rankings, matrix.scores, repo_cards
    )
    return matrix.model_copy(
        update={
            "weights": new_weights,
            "rankings": rankings,
            "recommendation": recommendation,
            "limitations": limitations,
            "recommendation_evidence_ids": evidence_ids,
            "generated_at": datetime.now(timezone.utc),
        }
    )


class ComparisonService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ComparisonRepository(session)

    def get_by_task(self, task_id: str) -> ComparisonMatrix | None:
        return self.repo.get_by_task(task_id)

    def recompute_weights(
        self,
        task_id: str,
        weights: dict[str, float],
        repo_cards: list[RepoCard],
    ) -> ComparisonMatrix:
        matrix = self.repo.get_by_task(task_id)
        if matrix is None:
            raise ValueError("comparison not found")
        updated = recompute_matrix(matrix, weights, repo_cards)
        return self.repo.upsert_by_task(updated)


def default_weights() -> dict[str, float]:
    return dict(DEFAULT_RUBRIC_WEIGHTS)
