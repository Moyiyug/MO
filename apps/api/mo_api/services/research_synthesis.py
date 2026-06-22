"""ResearchSynthesisService：聚合材料生成研究综合与质量评分（PRD F4 / F8）。

只综合已有材料，不创建新 evidence。失败时安全降级，不阻断报告生成。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session

from ..adapters.model_gateway.gateway import ModelGateway
from ..models.research_synthesis import ResearchQuality, ResearchSynthesis
from .report_context import ReportContext
from .report_evidence import EvidenceDigest
from .report_seed_service import ReportSeedService

logger = logging.getLogger("mo_api.research_synthesis")


def extract_seed_field(
    report_seeds: list, field: str
) -> list[dict[str, Any]]:
    """从 report_seeds 列表的 structured_data 中提取指定 JSON 字段。"""
    result: list[dict[str, Any]] = []
    for seed in report_seeds:
        sd = getattr(seed, "structured_data", None) or {}
        if field in sd:
            val = sd[field]
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        result.append(item)
            elif isinstance(val, str) and val.strip():
                result.append({field: val})
            elif isinstance(val, dict):
                result.append(val)
    return result


def extract_single_seed_field(
    report_seeds: list, field: str
) -> str | None:
    """从 report_seeds 的 structured_data 中提取单个字符串字段。"""
    for seed in report_seeds:
        sd = getattr(seed, "structured_data", None) or {}
        val = sd.get(field)
        if isinstance(val, str) and val.strip():
            return val
    return None


def parse_json_object(raw: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON，容忍 markdown fence 和多余空白。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.debug("research synthesis JSON parse failed: %s", text[:200])
    return {}


def format_digest_for_prompt(digest: EvidenceDigest) -> str:
    """将 EvidenceDigest 格式化为 prompt 友好的文字。"""
    lines: list[str] = []
    lines.append(f"共 {len(digest.refs)} 条证据，其中 {len(digest.weak_or_missing_ids)} 条 weak/missing。")
    for ref in digest.refs[:20]:
        lines.append(
            f"- {ref.display_id} [{ref.strength.value}] {ref.source_type.value}: "
            f"{ref.summary[:200]}"
        )
    return "\n".join(lines)


def build_research_synthesis_prompt(
    context: ReportContext,
    quality: ResearchQuality,
    evidence_digest: EvidenceDigest,
) -> str:
    """构建研究综合 prompt（PRD F4）。"""
    paperqa_answers = extract_seed_field(context.report_seeds, "paperqa_answers")
    web_report = extract_single_seed_field(context.report_seeds, "web_report")
    repo_cards = [card.model_dump(mode="json") for card in context.repo_cards]
    comparison = (
        context.comparison.model_dump(mode="json") if context.comparison else None
    )
    reproducibility = (
        context.reproducibility.model_dump(mode="json")
        if context.reproducibility
        else None
    )

    return f"""
你是 MO 的研究综合器，不是证据生成器。

硬性规则：
1. 只能基于输入材料综合观点，不能新增材料中不存在的事实。
2. 没有 run_log 时，不得声称复现成功、实测通过、实际运行成功。
3. weak/missing evidence 支持的内容必须进入 uncertainty。
4. recommendation 只能作为需要用户审阅的建议，不得写成最终审批结论。
5. 输出 JSON，不要输出 Markdown fence。

输出 schema：
{{
  "thesis": "...",
  "key_insights": ["..."],
  "repo_interpretations": {{"repo_name": "..."}},
  "tradeoffs": ["..."],
  "uncertainty": ["..."],
  "next_questions": ["..."],
  "evidence_ids": ["..."]
}}

task_goal:
{context.task.goal}

research_quality:
{quality.model_dump_json()}

repo_cards:
{json.dumps(repo_cards, ensure_ascii=False)[:10000]}

paperqa_answers:
{json.dumps(paperqa_answers, ensure_ascii=False)[:10000]}

web_report:
{str(web_report or "")[:6000]}

comparison:
{json.dumps(comparison, ensure_ascii=False)[:8000]}

reproducibility:
{json.dumps(reproducibility, ensure_ascii=False)[:8000]}

evidence_digest:
{format_digest_for_prompt(evidence_digest)}
""".strip()


class ResearchSynthesisService:
    """研究综合服务（PRD F4 / F8）。"""

    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def synthesize(
        self,
        context: ReportContext,
        *,
        evidence_digest: EvidenceDigest,
    ) -> tuple[ResearchSynthesis, ResearchQuality, list[str]]:
        """执行研究综合，返回 synthesis、quality 和 warnings。"""
        quality = self.evaluate_quality(context, evidence_digest=evidence_digest)
        prompt = build_research_synthesis_prompt(context, quality, evidence_digest)
        try:
            profile = self.gateway.select(
                need_reasoning=True, need_json=True, long_context=True
            )
            raw = await self.gateway.complete(
                profile,
                [{"role": "user", "content": prompt}],
                max_tokens=3000,
                json_mode=True,
            )
            data = parse_json_object(raw)
            synthesis = ResearchSynthesis.model_validate(data)
            synthesis = self._enforce_boundaries(synthesis, context, evidence_digest)
            return synthesis, quality, []
        except (ValidationError, ValueError, Exception) as exc:
            logger.warning("research synthesis failed: %s", exc)
            fallback = self._fallback_synthesis(context, quality)
            return (
                fallback,
                quality,
                [f"研究综合生成失败，已使用安全降级摘要：{str(exc)[:120]}"],
            )

    def evaluate_quality(
        self,
        context: ReportContext,
        *,
        evidence_digest: EvidenceDigest,
    ) -> ResearchQuality:
        """确定性规则评分，不依赖 LLM（PRD F8）。"""
        paperqa_answers = (
            extract_seed_field(context.report_seeds, "paperqa_answers") or []
        )
        has_paperqa = any(
            a.get("answer") and not a.get("failed") for a in paperqa_answers
        )
        web_report = extract_single_seed_field(context.report_seeds, "web_report")
        weak_count = len(evidence_digest.weak_or_missing_ids)
        evidence_total = max(len(evidence_digest.refs), 1)
        coverage = max(0.0, min(1.0, 1 - weak_count / evidence_total))

        points = 0
        points += 1 if has_paperqa else 0
        points += 1 if web_report else 0
        points += 1 if len(context.repo_cards) >= 2 else 0
        points += 1 if context.comparison is not None else 0
        points += 1 if context.reproducibility is not None else 0
        points += 1 if coverage >= 0.7 else 0

        depth = "deep" if points >= 5 else "medium" if points >= 3 else "shallow"
        confidence = (
            "high"
            if points >= 5 and weak_count <= 2
            else "medium"
            if points >= 3
            else "low"
        )

        limitations: list[str] = []
        if not has_paperqa:
            limitations.append("PaperQA 未产生有效综合回答。")
        if not web_report:
            limitations.append("缺少联网调研报告或联网调研未启用。")
        if not any(
            e.source_type.value == "run_log" for e in context.evidence_items
        ):
            limitations.append("没有 run_log，复现相关判断仅限静态评估。")
        if weak_count:
            limitations.append(f"存在 {weak_count} 条 weak/missing 证据。")

        return ResearchQuality(
            research_depth=depth,
            confidence_level=confidence,
            evidence_coverage=coverage,
            limitations=limitations,
            has_paperqa_answer=has_paperqa,
            has_web_report=bool(web_report),
            repo_card_count=len(context.repo_cards),
            has_comparison=context.comparison is not None,
            has_reproducibility=context.reproducibility is not None,
            weak_or_missing_evidence_count=weak_count,
        )

    def _enforce_boundaries(
        self,
        synthesis: ResearchSynthesis,
        context: ReportContext,
        digest: EvidenceDigest,
    ) -> ResearchSynthesis:
        """强制证据边界：移除不在 digest 中的 evidence_ids，补充安全不确定性。"""
        known_ids = set(digest.by_id.keys())
        valid_eids = [eid for eid in synthesis.evidence_ids if eid in known_ids]
        if not synthesis.uncertainty:
            synthesis.uncertainty = []
        has_run_log = any(
            e.source_type.value == "run_log" for e in context.evidence_items
        )
        if not has_run_log:
            synthesis.uncertainty.append(
                "复现相关判断均为静态评估，未经实际运行验证。"
            )
        if len(digest.weak_or_missing_ids) > 0 and not any(
            "弱证据" in u or "缺失" in u or "不足" in u
            for u in synthesis.uncertainty
        ):
            synthesis.uncertainty.append(
                f"存在 {len(digest.weak_or_missing_ids)} 条弱/缺失证据，部分结论可靠性受限。"
            )
        synthesis.evidence_ids = valid_eids
        return synthesis

    def _fallback_synthesis(
        self,
        context: ReportContext,
        quality: ResearchQuality,
    ) -> ResearchSynthesis:
        """安全降级：基于确定性信息构建 fallback synthesis。"""
        goal = context.task.goal or "本次调研"
        repo_names = [c.repo_name for c in context.repo_cards]
        repo_list = "、".join(repo_names) if repo_names else "候选仓库"

        thesis = (
            f"围绕「{goal}」，系统已完成对 {repo_list} 的仓库分析、"
            f"资料调研和对比评估。由于研究综合模型暂时不可用，"
            f"当前结论基于已收集的结构化数据自动生成，"
            f"建议结合数据视图进行人工确认。"
        )
        key_insights = [
            f"已完成 {len(context.repo_cards)} 个仓库的结构化分析。",
            f"共收集 {len(context.evidence_items)} 条证据。",
        ]
        if context.comparison and hasattr(context.comparison, "rankings"):
            rankings = context.comparison.rankings
            if rankings:
                key_insights.append(
                    f"对比排名第一：{rankings[0].repo_name}。"
                )
        repo_interpretations = {
            c.repo_name: f"已采集 {len(c.evidence_ids) if c.evidence_ids else 0} 条证据。"
            for c in context.repo_cards[:5]
        }
        tradeoffs = [
            "研究综合模型不可用，请以对比矩阵和数据视图为准。"
        ]
        uncertainty = [
            "研究综合由 fallback 算法生成，未经过 LLM 提炼。",
            "建议切换到数据视图检查完整结构化依据。",
        ]
        next_questions = [
            "切换到数据视图查看完整证据与章节依据。",
            "结合对比矩阵和场景化建议进行人工判断。",
        ]

        return ResearchSynthesis(
            thesis=thesis,
            key_insights=key_insights,
            repo_interpretations=repo_interpretations,
            tradeoffs=tradeoffs,
            uncertainty=uncertainty,
            next_questions=next_questions,
            evidence_ids=[],
        )


def write_synthesis_seeds(
    session: Session,
    *,
    task_id: str,
    synthesis: ResearchSynthesis,
    quality: ResearchQuality,
    warnings: list[str],
) -> None:
    """将 synthesis 和 quality 写入多个 section seeds（PRD F4）。"""
    service = ReportSeedService(session)
    payload = {
        "research_synthesis": synthesis.model_dump(mode="json"),
        "research_quality": quality.model_dump(mode="json"),
    }
    mapping: dict[str, str] = {
        "task_background": synthesis.thesis,
        "paper_supplement": "\n".join(synthesis.key_insights),
        "repo_overview": "\n".join(
            f"{name}: {text}"
            for name, text in synthesis.repo_interpretations.items()
        ),
        "comparison_matrix": "\n".join(synthesis.tradeoffs),
        "recommendation": "\n".join(
            synthesis.tradeoffs + synthesis.uncertainty
        ),
        "next_steps": "\n".join(synthesis.next_questions),
    }
    for section_key, narrative in mapping.items():
        service.upsert_seed(
            task_id=task_id,
            section_key=section_key,
            node="research_synthesis",
            narrative_seed=narrative or synthesis.thesis,
            structured_data=payload,
            evidence_ids=synthesis.evidence_ids,
            warnings=warnings + quality.limitations,
        )
