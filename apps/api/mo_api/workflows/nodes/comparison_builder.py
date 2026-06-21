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
from ...services.report_seed_service import ReportSeedService
from ...storage import db
from ...storage.repositories import ComparisonRepository, PlanRepository, RepoCardRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..state import MOState

NODE_ID = "comparison_builder"


def _parse_score(raw: str) -> tuple[float, str]:
    text = raw.strip()
    # Strip ALL markdown code block wrappers (not just at start)
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```", "", text)
    text = text.strip()
    # Find the first JSON object in the text
    json_start = text.find("{")
    if json_start >= 0:
        depth = 0
        json_end = -1
        for i in range(json_start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    json_end = i + 1
                    break
        if json_end > json_start:
            try:
                data = json.loads(text[json_start:json_end])
                if isinstance(data, dict):
                    score = float(data.get("score", 0.5))
                    rationale = str(data.get("rationale", ""))
                    return max(0.0, min(1.0, score)), rationale
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.debug("JSON parse failed for substring: %s", text[json_start:json_end][:100])
    # Regex fallback
    match = re.search(r'"score"\s*:\s*([\d.]+)', text)
    score = float(match.group(1)) if match else 0.5
    rationale_match = re.search(r'"rationale"\s*:\s*"([^"]*)"', text)
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


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def _has_rag_signal(card: RepoCard) -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            card.repo_name,
            card.summary,
            card.project_type,
            " ".join(card.docs_paths or []),
        )
    ).lower()
    return any(
        token in text
        for token in (
            "rag",
            "retrieval",
            "llm",
            "language model",
            "index",
            "pipeline",
            "agent",
        )
    )


def _fallback_dimension_score(card: RepoCard, dimension: str) -> tuple[float, str]:
    docs_count = len(card.docs_paths or [])
    deps_count = len(card.dependencies or [])
    entry_count = len(card.entrypoints or [])
    tests_count = len(card.test_commands or [])
    risks_count = len(card.risks or [])
    has_license = bool(card.license)
    has_type = bool(card.project_type)
    has_language = bool(card.primary_language)
    has_summary = bool(card.summary)
    has_rag = _has_rag_signal(card)

    if dimension == "technical_route":
        score = (
            0.35
            + (0.18 if has_type else 0.0)
            + (0.14 if has_language else 0.0)
            + min(entry_count, 3) * 0.07
            + (0.06 if deps_count else 0.0)
        )
    elif dimension == "documentation":
        score = (
            0.35
            + min(docs_count, 3) * 0.12
            + (0.12 if has_summary else 0.0)
            + (0.07 if has_license else 0.0)
        )
    elif dimension == "reproducibility":
        score = (
            0.30
            + (0.18 if tests_count else 0.0)
            + (0.14 if docs_count else 0.0)
            + (0.10 if deps_count else 0.0)
            + (0.08 if entry_count else 0.0)
            - min(risks_count, 4) * 0.04
        )
    elif dimension == "engineering_fit":
        score = (
            0.35
            + (0.12 if deps_count else 0.0)
            + (0.12 if entry_count else 0.0)
            + (0.12 if tests_count else 0.0)
            + (0.10 if has_license else 0.0)
            + (0.08 if has_type else 0.0)
            - min(risks_count, 4) * 0.04
        )
    elif dimension == "research_value":
        score = (
            0.42
            + (0.18 if has_rag else 0.0)
            + (0.10 if docs_count else 0.0)
            + (0.08 if has_summary else 0.0)
            + (0.06 if has_type else 0.0)
        )
    elif dimension == "extensibility":
        score = (
            0.35
            + (0.15 if entry_count else 0.0)
            + (0.12 if tests_count else 0.0)
            + (0.10 if docs_count else 0.0)
            + (0.08 if has_type else 0.0)
            + (0.06 if deps_count else 0.0)
        )
    elif dimension == "risks":
        score = 0.82 - min(risks_count, 5) * 0.10 + (0.04 if has_license else 0.0)
    elif dimension == "recommended_use_case":
        score = (
            0.38
            + (0.14 if docs_count else 0.0)
            + (0.12 if entry_count else 0.0)
            + (0.10 if has_rag else 0.0)
            + (0.08 if has_summary else 0.0)
        )
    else:
        score = 0.5

    rationale = (
        "LLM 未返回可用评分理由，已改用 RepoCard 信号做保守估算："
        f"docs={docs_count}, deps={deps_count}, entrypoints={entry_count}, "
        f"test_commands={tests_count}, risks={risks_count}, "
        f"license_present={1 if has_license else 0}, "
        f"project_type={'yes' if has_type else 'no'}。"
    )
    rationale = (
        rationale.replace("project_type=yes", "project_type_present=1")
        .replace("project_type=no", "project_type_present=0")
        .replace("ĄŁ", ".")
    )
    rationale = (
        f"RepoCard保守估算：docs={docs_count}, deps={deps_count}, "
        f"entries={entry_count}, tests={tests_count}, risks={risks_count}, "
        f"license={1 if has_license else 0}, type={1 if has_type else 0}."
    )
    return _clamp(score), rationale


def _needs_score_fallback(score: float, rationale: str) -> bool:
    text = (rationale or "").strip()
    if not text:
        return True
    weak_markers = {
        "评分依据不足",
        "insufficient evidence",
        "not enough information",
    }
    if text.startswith("{") or '"score"' in text or "'score'" in text:
        return True
    if len(text) < 16:
        return True
    return any(marker.lower() in text.lower() for marker in weak_markers)


async def comparison_builder(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

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
                    json_mode=True,
                )
                score_val, rationale = _parse_score(raw)
                if _needs_score_fallback(score_val, rationale):
                    score_val, rationale = _fallback_dimension_score(card, dimension)

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
                score_val, rationale = _fallback_dimension_score(card, dimension)
                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.MODEL_INFERENCE,
                    source_uri=card.repo_url,
                    locator=f"comparison:{dimension}:fallback",
                    quote_or_summary=(
                        f"[{dimension}] score={score_val:.2f}: {rationale[:500]}"
                    ),
                    strength=EvidenceStrength.WEAK,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                all_evidence_ids.append(eid)
                scores.append(
                    DimensionScore(
                        dimension=dimension,
                        repo_url=card.repo_url,
                        score=score_val,
                        rationale=rationale,
                        evidence_ids=[eid],
                        label=ClaimLabel.INFERENCE,
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

    try:
        top = rankings[0] if rankings else None
        compare_seed = [
            f"本次对比覆盖 {len(repo_cards)} 个仓库，使用 {len(COMPARISON_DIMENSIONS)} 个维度。"
        ]
        if top:
            compare_seed.append(
                f"当前权重下排名第一的是 {top.repo_name}，加权总分 {top.weighted_total:.2f}。"
            )
        if limitations:
            compare_seed.append(
                f"该对比存在 {len(limitations)} 项局限，需要用户结合场景确认。"
            )

        rec_seed = matrix.recommendation or "推荐结论尚不充分。"
        with Session(db.get_engine()) as session:
            seed_service = ReportSeedService(session)
            seed_service.upsert_seed(
                task_id=task_id,
                section_key="comparison_matrix",
                node=NODE_ID,
                narrative_seed="\n".join(compare_seed),
                structured_data=matrix.model_dump(mode="json"),
                evidence_ids=all_evidence_ids,
                warnings=limitations,
            )
            seed_service.upsert_seed(
                task_id=task_id,
                section_key="recommendation",
                node=NODE_ID,
                narrative_seed=rec_seed,
                structured_data={
                    "recommendation": matrix.recommendation,
                    "rankings": [r.model_dump(mode="json") for r in rankings],
                    "limitations": limitations,
                },
                evidence_ids=rec_evidence,
                warnings=limitations,
            )
    except Exception as exc:
        logger.warning("comparison/recommendation seed write failed: %s", exc)

    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "comparison": matrix.model_dump(mode="json"),
        "evidence_items": evidence_items,
    }
