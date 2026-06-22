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
from ...models.research_synthesis import PaperQAAnswerRecord
from ...services.report_seed_service import ReportSeedService
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
        json_mode=True,
    )
    return _parse_classification(raw)


def _build_deep_research_questions(goal: str, repo_names: list[str]) -> list[str]:
    """构建深度研究多问题集（PRD F2）。"""
    target = goal or "本次仓库调研目标"
    repos = "、".join(repo_names) if repo_names else "候选仓库"
    return [
        f"围绕「{target}」，这些资料给出的核心结论是什么？",
        f"这些资料如何解释 {repos} 的架构设计、核心抽象和适用边界？",
        f"这些资料指出了哪些工程成熟度、复现性、维护风险或使用限制？",
        f"如果要做多方案选型，这些资料支持哪些判断，哪些判断仍不充分？",
    ]


async def _query_paperqa_answers(
    ctx,
    *,
    doc_paths: list[str],
    questions: list[str],
    task_id: str,
    repo_urls: list[str],
    paper_urls: list[str],
    repo_cards: list,
) -> tuple[list[PaperQAAnswerRecord], list[PaperMaterial], list[str]]:
    """多问题查询 PaperQA，返回 answer records、materials 和 evidence ids（PRD F1 / F2）。"""
    answer_records: list[PaperQAAnswerRecord] = []
    materials: list[PaperMaterial] = []
    evidence_ids: list[str] = []

    for question in questions:
        try:
            answer = await ctx.paper_adapter.query_papers(
                doc_paths,
                question=question,
                task_id=task_id,
            )
        except PaperResearchError as exc:
            answer_records.append(
                PaperQAAnswerRecord(
                    question=question,
                    failed=True,
                    warning=str(exc)[:300],
                )
            )
            continue

        context_eids: list[str] = []
        source_names: list[str] = []
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
                context_eids.append(eid)
                source_names.append(c.source_name)
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

        answer_records.append(
            PaperQAAnswerRecord(
                question=question,
                answer=(answer.answer or "")[:4000],
                context_evidence_ids=context_eids,
                source_names=source_names,
                failed=False,
            )
        )

    return answer_records, materials, evidence_ids


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
    paperqa_answers: list[PaperQAAnswerRecord] = []
    web_report: str = ""
    web_sources: list[dict] = []

    # PaperQA 多问题深度查询（PRD F1 / F2）
    if doc_paths:
        repo_names = [c.repo_name for c in repo_cards]
        questions = _build_deep_research_questions(goal, repo_names)
        try:
            paperqa_answers, qa_materials, qa_evidence_ids = await _query_paperqa_answers(
                ctx,
                doc_paths=doc_paths,
                questions=questions,
                task_id=task_id,
                repo_urls=repo_urls,
                paper_urls=paper_urls,
                repo_cards=repo_cards,
            )
            materials.extend(qa_materials)
            evidence_ids.extend(qa_evidence_ids)
        except PaperResearchError:
            # PaperQA 完全不可用：对每个 paper URL 登记降级 evidence
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
            paperqa_answers.append(
                PaperQAAnswerRecord(
                    question="(全部查询失败)",
                    failed=True,
                    warning="PaperQA adapter 不可用",
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
                web_sources.append({"url": src.url, "summary": src.summary})
            if web_result.report:
                web_report = web_result.report[:6000]
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

    try:
        official = [
            material
            for material in materials
            if material.material_type.value in {"official_repo_paper", "official_doc"}
        ]
        pending = [
            material for material in materials if not material.relationship_clear
        ]

        # 构建解释型 narrative（PRD F1 / F3）
        narrative_lines: list[str] = []
        successful_answers = [a for a in paperqa_answers if a.answer and not a.failed]
        if successful_answers:
            narrative_lines.append("PaperQA 对资料的综合回答：")
            for a in successful_answers[:4]:
                narrative_lines.append(f"- {a.question}")
                narrative_lines.append(f"  {a.answer[:800]}")
        else:
            narrative_lines.append("PaperQA 未能生成有效综合回答，本节仅保留资料证据和待核实项。")

        if web_report:
            narrative_lines.append("")
            narrative_lines.append("联网调研摘要：")
            narrative_lines.append(web_report[:1200])

        # 统计信息作为补充
        narrative_lines.append("")
        narrative_lines.append(f"本次资料调研收集 {len(materials)} 项资料。")
        if official:
            narrative_lines.append(
                f"其中 {len(official)} 项被识别为官方论文或官方文档。"
            )
        if pending:
            narrative_lines.append(
                f"有 {len(pending)} 项资料与仓库关系尚不明确，需要后续确认。"
            )

        warnings_list = []
        if pending:
            warnings_list.append("存在资料关系不明项")
        if paperqa_answers and all(a.failed for a in paperqa_answers):
            warnings_list.append("所有 PaperQA 查询均失败")

        with Session(db.get_engine()) as session:
            ReportSeedService(session).upsert_seed(
                task_id=task_id,
                section_key="paper_supplement",
                node=NODE_ID,
                narrative_seed="\n".join(narrative_lines),
                structured_data={
                    "materials": [m.model_dump(mode="json") for m in materials],
                    "paperqa_answers": [a.model_dump(mode="json") for a in paperqa_answers],
                    "web_report": web_report,
                    "web_sources": web_sources,
                },
                evidence_ids=evidence_ids,
                warnings=warnings_list,
            )
    except Exception as exc:
        logger.warning("paper_supplement seed write failed: %s", exc)

    return {
        "paper_materials": [m.model_dump(mode="json") for m in materials],
        "evidence_items": evidence_items,
    }
