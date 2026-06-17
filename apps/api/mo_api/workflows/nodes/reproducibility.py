"""reproducibility 节点：静态复现评估（PRD F-007）。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("mo_api.reproducibility")

from sqlmodel import Session

from ...models.enums import (
    REPRO_DIMENSIONS,
    STATIC_REPRO_ASSESSMENT_LABEL,
    EvidenceStrength,
    NodeStatus,
    SourceType,
)
from ...models.evidence import EvidenceItem
from ...models.reproducibility import ReproducibilityReport, ReproducibilityScore
from ...storage import db
from ...storage.repositories import RepoCardRepository, ReproducibilityRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..state import MOState

NODE_ID = "reproducibility"


def _parse_dimension(raw: str) -> tuple[float, str, list[str]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            score = float(data.get("score", 0.5))
            reason = str(data.get("reason", ""))
            missing = data.get("missing_info") or []
            if isinstance(missing, str):
                missing = [missing]
            return max(0.0, min(1.0, score)), reason, list(missing)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.debug("JSON parse failed for LLM output: %s", text[:100])
    match = re.search(r'"score"\s*:\s*([\d.]+)', text)
    score = float(match.group(1)) if match else 0.5
    return max(0.0, min(1.0, score)), text[:200], []


def _card_signals(card) -> str:
    return "\n".join(
        [
            f"repo: {card.repo_url}",
            f"name: {card.repo_name}",
            f"dependencies: {', '.join(card.dependencies or [])}",
            f"entrypoints: {', '.join(card.entrypoints or [])}",
            f"test_commands: {', '.join(card.test_commands or [])}",
            f"docs_paths: {', '.join(card.docs_paths or [])}",
            f"license: {card.license or 'N/A'}",
            f"risks: {', '.join(card.risks or [])}",
            f"summary: {(card.summary or '')[:400]}",
        ]
    )


async def reproducibility(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="静态复现性评估",
        logs=["reproducibility analysis started"],
    )

    with Session(db.get_engine()) as session:
        repo_cards = RepoCardRepository(session).list_by_task(task_id)

    if not repo_cards:
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.SKIPPED,
            input_summary="无仓库可评估",
            logs=["reproducibility skipped: no repo cards"],
        )
        return {"reproducibility": None}

    profile = ctx.model_gateway.select(need_reasoning=True, need_json=True)
    scores: list[ReproducibilityScore] = []
    all_evidence_ids: list[str] = []

    for card in repo_cards:
        context = _card_signals(card)
        dimension_scores: dict[str, float] = {}
        reasons: list[str] = []
        missing_info: list[str] = []
        card_evidence: list[str] = []

        for dimension in REPRO_DIMENSIONS:
            try:
                prompt = (
                    f'Score reproducibility dimension "{dimension}" from 0.0 to 1.0 '
                    "based ONLY on repo card data below. "
                    'Respond JSON: {"score": 0.0-1.0, "reason": "...", "missing_info": ["..."]}\n\n'
                    f"{context}"
                )
                raw = await ctx.model_gateway.complete(
                    profile,
                    [{"role": "user", "content": prompt}],
                    max_tokens=256,
                )
                score_val, reason, missing = _parse_dimension(raw)
                dimension_scores[dimension] = score_val
                if reason:
                    reasons.append(f"{dimension}: {reason}")
                missing_info.extend(missing)

                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.MODEL_INFERENCE,
                    source_uri=card.repo_url,
                    locator=f"repro:{dimension}",
                    quote_or_summary=f"[{dimension}] score={score_val:.2f}: {reason[:500]}",
                    strength=EvidenceStrength.MEDIUM,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                card_evidence.append(eid)
                all_evidence_ids.append(eid)
            except Exception as exc:
                logger.warning("repro dim %s/%s failed: %s", card.repo_url, dimension, exc)
                dimension_scores[dimension] = 0.0
                reasons.append(f"{dimension}: 评分失败（LLM 调用异常）")

        overall = (
            sum(dimension_scores.values()) / len(dimension_scores)
            if dimension_scores
            else 0.0
        )
        next_checks = [
            "Run smoke test with user approval (M10 sandbox)",
            "Verify install commands against fresh environment",
        ]
        if not card.test_commands:
            next_checks.append("Locate or document test commands")
            missing_info.append("test_commands not found")

        scores.append(
            ReproducibilityScore(
                repo_url=card.repo_url,
                repo_name=card.repo_name,
                overall_score=round(overall, 4),
                dimension_scores=dimension_scores,
                reasons=reasons[:10],
                missing_info=list(dict.fromkeys(missing_info))[:10],
                recommended_next_checks=next_checks,
                evidence_ids=card_evidence,
                assessment_label=STATIC_REPRO_ASSESSMENT_LABEL,
            )
        )

    report = ReproducibilityReport(
        id=uuid.uuid4().hex,
        task_id=task_id,
        scores=scores,
        generated_at=datetime.now(timezone.utc),
    )

    with Session(db.get_engine()) as session:
        ReproducibilityRepository(session).upsert_by_task(report)

    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "reproducibility": report.model_dump(mode="json"),
        "evidence_items": evidence_items,
    }
