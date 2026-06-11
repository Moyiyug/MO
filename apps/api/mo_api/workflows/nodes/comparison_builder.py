"""comparison_builder 节点：多仓库 8 维对比打分与加权排名。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("mo_api.comparison_builder")

from sqlmodel import Session

from ...models.comparison import (
    COMPARISON_DIMENSIONS,
    ComparisonMatrix,
    DimensionScore,
)
from ...models.enums import ClaimLabel, EvidenceStrength, NodeStatus, SourceType
from ...models.evidence import EvidenceItem
from ...models.repo import RepoCard
from ...services.comparison_service import (
    build_recommendation,
    compute_rankings,
    default_weights,
)
from ...storage import db
from ...storage.repositories import ComparisonRepository, PlanRepository, RepoCardRepository
from ..execute_context import get_context, publish_node_event
from ..state import MOState

NODE_ID = "comparison_builder"


def _parse_score(raw: str) -> tuple[float, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            score = float(data.get("score", 0.5))
            rationale = str(data.get("rationale", ""))
            return max(0.0, min(1.0, score)), rationale
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.debug("JSON parse failed for LLM output: %s", text[:100])
    match = re.search(r'"score"\s*:\s*([\d.]+)', text)
    score = float(match.group(1)) if match else 0.5
    rationale_match = re.search(r'"rationale"\s*:\s*"([^"]+)"', text)
    rationale = rationale_match.group(1) if rationale_match else text[:200]
    return max(0.0, min(1.0, score)), rationale


def _card_context(card: RepoCard, code_insights: list[dict]) -> str:
    lines = [
        f"repo: {card.repo_url}",
        f"name: {card.repo_name}",
        f"language: {card.primary_language}",
        f"type: {card.project_type}",
        f"entrypoints: {', '.join(card.entrypoints)}",
        f"test_commands: {', '.join(card.test_commands)}",
        f"docs: {', '.join(card.docs_paths)}",
        f"license: {card.license}",
        f"risks: {', '.join(card.risks)}",
        f"summary: {card.summary[:400]}",
    ]
    for ins in code_insights:
        if ins.get("repo_url") == card.repo_url:
            lines.append(f"insight: {ins}")
    return "\n".join(lines)


async def comparison_builder(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)

    with Session(db.get_engine()) as session:
        repo_cards = RepoCardRepository(session).list_by_task(task_id)

    if len(repo_cards) < 2:
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.SKIPPED,
            input_summary="仓库不足 2 个，跳过对比",
            logs=["comparison skipped: fewer than 2 repos"],
        )
        # 清理此前可能存在的旧对比数据
        with Session(db.get_engine()) as session:
            ComparisonRepository(session).delete_by_task(task_id)
        return {"comparison": None}

    repo_cards = repo_cards[:5]
    code_insights = list(state.get("code_insights") or [])

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary=f"对比 {len(repo_cards)} 个仓库",
        logs=["comparison builder started"],
    )

    with Session(db.get_engine()) as session:
        plan = PlanRepository(session).get_latest_by_task(task_id)
    weights = (
        dict(plan.report_rubric.weights)
        if plan
        else default_weights()
    )

    profile = ctx.model_gateway.select(need_reasoning=True, need_json=True)
    scores: list[DimensionScore] = []
    all_evidence_ids: list[str] = []

    for card in repo_cards:
        context = _card_context(card, code_insights)
        for dimension in COMPARISON_DIMENSIONS:
            try:
                prompt = (
                    f'Score repo on dimension "{dimension}" from 0.0 to 1.0 '
                    "based ONLY on the data below. "
                    'Respond JSON: {"score": 0.0-1.0, "rationale": "..."}\n\n'
                    f"{context}"
                )
                raw = await ctx.model_gateway.complete(
                    profile,
                    [{"role": "user", "content": prompt}],
                    max_tokens=256,
                )
                score_val, rationale = _parse_score(raw)

                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.MODEL_INFERENCE,
                    source_uri=card.repo_url,
                    locator=f"comparison:{dimension}",
                    quote_or_summary=(
                        f"[{dimension}] score={score_val:.2f}: {rationale[:500]}"
                    ),
                    strength=EvidenceStrength.MEDIUM,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                all_evidence_ids.append(eid)

                label = ClaimLabel.INFERENCE if rationale else ClaimLabel.PENDING
                scores.append(
                    DimensionScore(
                        dimension=dimension,
                        repo_url=card.repo_url,
                        score=score_val,
                        rationale=rationale or "评分依据不足",
                        evidence_ids=[eid] if rationale else [],
                        label=label,
                    )
                )
            except Exception as exc:
                logger.warning("comparison dim %s/%s failed: %s", card.repo_url, dimension, exc)
                scores.append(
                    DimensionScore(
                        dimension=dimension,
                        repo_url=card.repo_url,
                        score=0.0,
                        rationale="评分失败（LLM 调用异常）",
                        evidence_ids=[],
                        label=ClaimLabel.PENDING,
                    )
                )

    try:
        rankings = compute_rankings(scores, repo_cards, weights)
        recommendation, limitations, rec_evidence = build_recommendation(
            rankings, scores, repo_cards
        )
    except Exception as exc:
        logger.warning("comparison compute_rankings failed: %s", exc)
        from ...services.comparison_service import RepoRanking
        rankings = [
            RepoRanking(
                repo_url=c.repo_url,
                repo_name=c.repo_name,
                weighted_total=0.0,
                per_dimension={},
            )
            for c in repo_cards
        ]
        recommendation = "加权计算失败，请检查对比数据完整性"
        limitations = ["排名计算异常"]
        rec_evidence = []
    all_evidence_ids.extend(rec_evidence)

    matrix = ComparisonMatrix(
        id=uuid.uuid4().hex,
        task_id=task_id,
        repo_urls=[c.repo_url for c in repo_cards],
        dimensions=list(COMPARISON_DIMENSIONS),
        weights=weights,
        scores=scores,
        rankings=rankings,
        recommendation=recommendation,
        limitations=limitations,
        recommendation_evidence_ids=rec_evidence,
        generated_at=datetime.now(timezone.utc),
    )

    with Session(db.get_engine()) as session:
        ComparisonRepository(session).upsert_by_task(matrix)

    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "comparison": matrix.model_dump(mode="json"),
        "evidence_items": evidence_items,
    }
