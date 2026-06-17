"""paper_research 节点：论文 RAG + 可选联网调研（PRD F-006）。"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger("mo_api.paper_research")
import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from ...adapters.paper_research import PaperResearchError
from ...models.enums import EvidenceStrength, MaterialType, NodeStatus, SourceType
from ...models.evidence import EvidenceItem
from ...models.reproducibility import PaperMaterial
from ...storage import db
from ...storage.repositories import RepoCardRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..state import MOState

NODE_ID = "paper_research"


def _parse_classification(raw: str) -> tuple[MaterialType, bool]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            mt = str(data.get("material_type", "unverified_reference"))
            rel = bool(data.get("relationship_clear", False))
            try:
                return MaterialType(mt), rel
            except ValueError:
                return MaterialType.UNVERIFIED_REFERENCE, False
    except json.JSONDecodeError:
        logger.debug("JSON parse failed for LLM output: %s", text[:100])
    if "official_repo_paper" in text:
        return MaterialType.OFFICIAL_REPO_PAPER, True
    if "official_doc" in text:
        return MaterialType.OFFICIAL_DOC, True
    if "background_reference" in text:
        return MaterialType.BACKGROUND_REFERENCE, True
    if "model_suggested_reference" in text:
        return MaterialType.MODEL_SUGGESTED_REFERENCE, False
    return MaterialType.UNVERIFIED_REFERENCE, False


async def _classify_material(
    ctx,
    *,
    source_uri: str,
    summary: str,
    repo_urls: list[str],
    is_user_paper: bool,
    from_web: bool,
) -> tuple[MaterialType, bool]:
    if from_web:
        return MaterialType.BACKGROUND_REFERENCE, True
    if not is_user_paper:
        if any(p in summary.lower() for p in ("readme", "docs/", "documentation")):
            return MaterialType.OFFICIAL_DOC, True
        return MaterialType.MODEL_SUGGESTED_REFERENCE, False

    profile = ctx.model_gateway.select(need_reasoning=True, need_json=True)
    prompt = (
        "Classify this research material. Respond JSON only:\n"
        '{"material_type": "official_repo_paper|official_doc|background_reference|'
        'model_suggested_reference|unverified_reference", "relationship_clear": true|false}\n\n'
        f"source_uri: {source_uri}\n"
        f"repo_urls: {', '.join(repo_urls)}\n"
        f"summary: {summary[:500]}\n"
        "If repo-paper relationship is unclear, set relationship_clear=false."
    )
    raw = await ctx.model_gateway.complete(
        profile,
        [{"role": "user", "content": prompt}],
        max_tokens=128,
    )
    return _parse_classification(raw)


async def paper_research(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    goal = state.get("goal", "")
    ctx = get_context(task_id)
    permissions = state.get("permissions") or {}
    allow_web = bool(permissions.get("allow_web_search", False))
    paper_urls = list(state.get("paper_urls") or [])
    repo_urls = list(state.get("repo_urls") or [])

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="论文与资料调研",
        logs=["paper research started"],
    )

    # 收集 repo docs_paths + README 文件作为 PaperQA 输入
    with Session(db.get_engine()) as session:
        repo_cards = RepoCardRepository(session).list_by_task(task_id)
    doc_paths: list[str] = list(paper_urls)
    for card in repo_cards:
        for dp in card.docs_paths:
            doc_paths.append(dp)

    materials: list[PaperMaterial] = []
    evidence_ids: list[str] = []

    # 用 PaperQA 查询所有文档（URL + 本地路径）
    if doc_paths:
        try:
            answer = await ctx.paper_adapter.query_papers(
                doc_paths, question=goal or "summarize research documents", task_id=task_id
            )
            if answer.contexts:
                for c in answer.contexts:
                    mt, rel_clear = await _classify_material(
                        ctx,
                        source_uri=c.source_name,
                        summary=c.text,
                        repo_urls=repo_urls,
                        is_user_paper=c.source_name in paper_urls,
                        from_web=False,
                    )
                    if not rel_clear:
                        mt = MaterialType.UNVERIFIED_REFERENCE
                    # 尝试匹配关联仓库
                    related_repo = None
                    for card in repo_cards:
                        if card.repo_url in c.source_name or c.source_name in card.repo_url:
                            related_repo = card.repo_url
                            break
                    item = EvidenceItem(
                        id=uuid.uuid4().hex,
                        task_id=task_id,
                        source_type=SourceType.PAPER,
                        source_uri=c.source_name,
                        locator=c.locator,
                        quote_or_summary=c.text[:2000],
                        strength=EvidenceStrength.MEDIUM,
                        material_type=mt,
                        created_at=datetime.now(timezone.utc),
                    )
                    eid = ctx.evidence_service.add(item)
                    evidence_ids.append(eid)
                    materials.append(
                        PaperMaterial(
                            source_uri=c.source_name,
                            material_type=mt,
                            evidence_id=eid,
                            related_repo_url=related_repo,
                            relationship_clear=rel_clear,
                            summary=c.text[:300],
                        )
                    )
        except PaperResearchError:
            # PaperQA 不可用：对每个 URL 登记降级 evidence
            for url in paper_urls:
                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.PAPER,
                    source_uri=url,
                    locator="paper_url",
                    quote_or_summary=f"Paper URL pending deep research: {url}",
                    strength=EvidenceStrength.MISSING,
                    material_type=MaterialType.UNVERIFIED_REFERENCE,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                evidence_ids.append(eid)
                materials.append(
                    PaperMaterial(
                        source_uri=url,
                        material_type=MaterialType.UNVERIFIED_REFERENCE,
                        evidence_id=eid,
                        relationship_clear=False,
                        summary=url,
                    )
                )
    else:
        # 无文档路径：仅登记 paper_urls 为待调研
        for url in paper_urls:
            item = EvidenceItem(
                id=uuid.uuid4().hex,
                task_id=task_id,
                source_type=SourceType.PAPER,
                source_uri=url,
                locator="paper_url",
                quote_or_summary=f"Paper URL pending deep research: {url}",
                strength=EvidenceStrength.MISSING,
                material_type=MaterialType.UNVERIFIED_REFERENCE,
                created_at=datetime.now(timezone.utc),
            )
            eid = ctx.evidence_service.add(item)
            evidence_ids.append(eid)
            materials.append(
                PaperMaterial(
                    source_uri=url,
                    material_type=MaterialType.UNVERIFIED_REFERENCE,
                    evidence_id=eid,
                    relationship_clear=False,
                    summary=url,
                )
            )

    if allow_web and goal:
        try:
            web_result = await ctx.web_adapter.research(goal)
            for src in web_result.sources:
                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.WEB,
                    source_uri=src.url,
                    locator="web_research",
                    quote_or_summary=src.summary[:2000],
                    strength=EvidenceStrength.MEDIUM,
                    material_type=MaterialType.BACKGROUND_REFERENCE,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                evidence_ids.append(eid)
                materials.append(
                    PaperMaterial(
                        source_uri=src.url,
                        material_type=MaterialType.BACKGROUND_REFERENCE,
                        evidence_id=eid,
                        relationship_clear=False,
                        summary=src.summary[:300],
                    )
                )
            if web_result.report:
                item = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task_id,
                    source_type=SourceType.WEB,
                    source_uri="web_research_report",
                    locator="summary",
                    quote_or_summary=web_result.report[:2000],
                    strength=EvidenceStrength.MEDIUM,
                    material_type=MaterialType.BACKGROUND_REFERENCE,
                    created_at=datetime.now(timezone.utc),
                )
                eid = ctx.evidence_service.add(item)
                evidence_ids.append(eid)
        except PaperResearchError:
            await publish_node_event(
                ctx,
                NODE_ID,
                NodeStatus.RUNNING,
                logs=["web research skipped: adapter unavailable"],
            )

    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "paper_materials": [m.model_dump(mode="json") for m in materials],
        "evidence_items": evidence_items,
    }
