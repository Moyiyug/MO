"""报告章节与全文润色服务。

润色层只负责表达编辑，不拥有 claim/evidence/score/ranking 的事实控制权。
Phase 3（PRD F5/F7）：深度研究报告叙事结构、安全 fallback、禁词校验。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from ..adapters.model_gateway.gateway import ModelGateway
from ..models.evidence import ReportClaim
from ..models.report import ReportSection
from ..models.research_synthesis import ResearchQuality, ResearchSynthesis

logger = logging.getLogger("mo_api.report_polish")

# ── 安全常量 ───────────────────────────────────────────────────────────

SAFE_SECTION_FALLBACK_ZH = (
    "本节阅读版生成失败。为避免将结构化数据误展示为正文，"
    "系统暂不展示自动整理后的段落。请切换到数据视图查看本节原始依据、结论和证据。"
)

FORBIDDEN_READER_TERMS = [
    "RepoCard",
    "model_inference",
    "source_uri",
    "raw evidence id",
    "static_reproducibility_assessment",
    "LLM 未返回",
    "score=",
    "docs=",
    "deps=",
    "entrypoints=",
    "M10 sandbox",
    "ReportSectionSeed",
    "structured_markdown",
]


class SectionDraft(BaseModel):
    key: str
    title: str
    structured_markdown: str
    seed_narratives: list[str] = Field(default_factory=list)
    claims: list[ReportClaim] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    is_pending: bool = False
    summary: str | None = None


class PolishedSection(BaseModel):
    key: str
    title: str
    reader_markdown: str
    summary: str | None = None
    polish_status: str = "polished"
    warnings: list[str] = Field(default_factory=list)


def parse_jsonish(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.debug("report polish JSON parse failed: %s", text[:200])
    return {}


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def extract_report_markdown(raw: str) -> str:
    text = (raw or "").strip()
    fence = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, re.DOTALL | re.I)
    if fence:
        text = fence.group(1).strip()
    heading = re.search(r"(?m)^#\s+", text)
    if heading:
        text = text[heading.start():].strip()
    if not text.startswith("#"):
        return ""
    return text


def has_required_report_sections(markdown: str) -> bool:
    """保留旧接口兼容性；Phase 3 后使用 validate_deep_research_markdown。"""
    return len(re.findall(r"(?m)^##\s+\d+\.", markdown)) >= 13


def validate_deep_research_markdown(markdown: str) -> list[str]:
    """深度研究报告校验（PRD F5）：返回错误列表，空列表表示通过。"""
    errors: list[str] = []
    text = (markdown or "").strip()
    if not text.startswith("#"):
        errors.append("missing title")
    if len(text) < 800:
        errors.append("too short")
    required_patterns = {
        "conclusion": r"结论|判断|Conclusion|Finding",
        "uncertainty": r"不确定|边界|限制|Uncertainty|Limitation",
        "next_steps": r"下一步|验证|Next",
    }
    for name, pattern in required_patterns.items():
        if not re.search(pattern, text, flags=re.I):
            errors.append(f"missing {name}")
    for term in FORBIDDEN_READER_TERMS:
        if term in text:
            errors.append(f"forbidden term: {term}")
    if re.search(r"(?m)^##\s*13\.", text):
        errors.append("contains evidence appendix section")
    return errors


def build_safe_deep_research_fallback(
    *,
    synthesis: ResearchSynthesis | None,
    quality: ResearchQuality | None,
    pending_warnings: list[str],
) -> str:
    """构建安全降级深度研究报告（PRD F7）。"""
    thesis = (
        synthesis.thesis
        if synthesis and synthesis.thesis
        else "本次研究综合结论生成失败。"
    )
    uncertainty = synthesis.uncertainty if synthesis else []
    next_questions = synthesis.next_questions if synthesis else []
    limitations = quality.limitations if quality else []

    parts = [
        "# MO 深度调研报告",
        "",
        "## 结论先行",
        thesis,
        "",
        "## 为什么是这个判断",
        "系统已保留仓库分析、资料调研、对比矩阵和复现评估数据。"
        "当前阅读版使用安全降级摘要，避免将结构化数据误展示为正文。",
        "",
        "## 候选方案如何理解",
        "请进入数据视图查看各仓库的结构化分析与章节依据。",
        "",
        "## 关键权衡",
        "当前无法稳定生成完整权衡叙事，请以对比页和数据视图为准。",
        "",
        "## 不确定性与边界",
    ]
    parts.extend(
        f"- {item}"
        for item in (uncertainty + limitations + pending_warnings)[:8]
    )
    parts.extend(["", "## 下一步验证路线"])
    parts.extend(
        f"{i}. {q}"
        for i, q in enumerate(
            next_questions[:6] or ["进入数据视图检查证据与结构化依据。"],
            1,
        )
    )
    return "\n".join(parts).strip() + "\n"


class SectionPolisher:
    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def polish(
        self,
        draft: SectionDraft,
        *,
        output_language: str,
    ) -> PolishedSection:
        profile = self.gateway.select(need_reasoning=True, long_context=True)
        prompt = build_section_polish_prompt(draft, output_language=output_language)
        try:
            raw = await self.gateway.complete(
                profile,
                [{"role": "user", "content": prompt}],
                max_tokens=1800,
                json_mode=True,
            )
            data = parse_jsonish(raw)
            reader = str(data.get("reader_markdown") or "").strip()
            summary = data.get("summary")
            warnings = _string_list(data.get("warnings"))
            if not reader:
                return self._fallback(draft, "empty polish result")
            return PolishedSection(
                key=draft.key,
                title=draft.title,
                reader_markdown=reader,
                summary=str(summary)[:500] if summary else draft.summary,
                warnings=warnings,
                polish_status="polished",
            )
        except Exception as exc:
            logger.warning("section polish failed for %s: %s", draft.key, exc)
            return self._fallback(draft, str(exc)[:200])

    def _fallback(self, draft: SectionDraft, reason: str) -> PolishedSection:
        return PolishedSection(
            key=draft.key,
            title=draft.title,
            reader_markdown=SAFE_SECTION_FALLBACK_ZH,
            summary=draft.summary or "本节阅读版暂不可用，结构化依据已保留在数据视图。",
            polish_status="fallback",
            warnings=[f"section polish fallback: {reason}"],
        )


class FinalReportPolisher:
    def __init__(self, gateway: ModelGateway) -> None:
        self.gateway = gateway

    async def polish_report(
        self,
        *,
        executive_summary: str | None,
        sections: list[ReportSection],
        pending_warnings: list[str],
        output_language: str,
        fallback_markdown: str,
        research_synthesis: ResearchSynthesis | None = None,
        research_quality: ResearchQuality | None = None,
    ) -> str:
        profile = self.gateway.select(need_reasoning=True, long_context=True)
        prompt = build_final_report_polish_prompt(
            executive_summary=executive_summary,
            sections=sections,
            pending_warnings=pending_warnings,
            output_language=output_language,
            research_synthesis=research_synthesis,
            research_quality=research_quality,
        )
        try:
            text = (
                await self.gateway.complete(
                    profile,
                    [{"role": "user", "content": prompt}],
                    max_tokens=6000,
                )
            ).strip()
            if not text:
                return fallback_markdown
            text = extract_report_markdown(text)
            # Phase 3: 使用深度研究校验替代 13 章强约束
            if not text or "## " not in text:
                logger.warning("final report polish returned non-report markdown")
                return fallback_markdown
            validation_errors = validate_deep_research_markdown(text)
            if validation_errors:
                logger.warning(
                    "deep research validation failed: %s",
                    "; ".join(validation_errors[:5]),
                )
                return fallback_markdown
            return text
        except Exception as exc:
            logger.warning("final report polish failed: %s", exc)
            return fallback_markdown


def build_section_polish_prompt(
    draft: SectionDraft,
    *,
    output_language: str,
) -> str:
    lang_instruction = "请用中文。" if output_language == "zh" else "Use English."
    claims = [claim.model_dump(mode="json") for claim in draft.claims]
    seed_narratives = (
        "\n".join("- " + seed[:1000] for seed in draft.seed_narratives)
        or "（无）"
    )
    return f"""
你是 MO 报告章节编辑器。{lang_instruction}

你只能润色表达，不能新增事实。

硬性规则：
1. 不得新增 structured_markdown 或 seed_narratives 中没有的信息。
2. 不得改变任何仓库名、分数、排名、风险、证据状态。
3. 不得删除 pending / weak / missing / requires_user_review 的含义。
4. 不得把 model_inference 写成 fact。
5. 无 run_log 时不得声称复现成功。
6. 不要输出 raw evidence id；如果输入中有 E01/E02 形式，可以保留。
7. 不要生成新的 claim。
8. 输出 JSON，不要输出 Markdown fence。

section_key: {draft.key}
title: {draft.title}
is_pending: {draft.is_pending}

seed_narratives:
{seed_narratives}

structured_markdown:
{draft.structured_markdown[:8000]}

claims_json:
{json.dumps(claims, ensure_ascii=False)[:4000]}

输出格式：
{{
  "summary": "本节 1-2 句摘要",
  "reader_markdown": "润色后的 Markdown",
  "warnings": []
}}
""".strip()


def build_final_report_polish_prompt(
    *,
    executive_summary: str | None,
    sections: list[ReportSection],
    pending_warnings: list[str],
    output_language: str,
    research_synthesis: ResearchSynthesis | None = None,
    research_quality: ResearchQuality | None = None,
) -> str:
    lang_instruction = "请用中文。" if output_language == "zh" else "Use English."
    section_text = "\n\n".join(
        f"## {section.title}\n{section.markdown[:5000]}" for section in sections
    )
    warnings_text = "\n".join(f"- {warning}" for warning in pending_warnings)

    synthesis_text = ""
    if research_synthesis:
        synthesis_text = f"""
research_synthesis:
- thesis: {research_synthesis.thesis[:2000]}
- key_insights: {json.dumps(research_synthesis.key_insights, ensure_ascii=False)[:3000]}
- tradeoffs: {json.dumps(research_synthesis.tradeoffs, ensure_ascii=False)[:2000]}
- uncertainty: {json.dumps(research_synthesis.uncertainty, ensure_ascii=False)[:2000]}
- next_questions: {json.dumps(research_synthesis.next_questions, ensure_ascii=False)[:2000]}
"""

    quality_text = ""
    if research_quality:
        quality_text = f"""
research_quality:
- research_depth: {research_quality.research_depth}
- confidence_level: {research_quality.confidence_level}
- limitations: {json.dumps(research_quality.limitations, ensure_ascii=False)[:2000]}
"""

    return f"""
你是 MO 最终报告编辑器。{lang_instruction}

你将收到已完成事实校验和证据标注的章节文本，以及研究综合结论和可信度评分。
你需要输出一份"结论先行、解释链清晰、证据可追溯但默认不打断阅读"的深度研究报告。

目标结构：
# MO 深度调研报告

## 结论先行

## 为什么是这个判断

## 候选方案如何理解

## 关键权衡

## 不确定性与边界

## 下一步验证路线

硬性规则：
1. 不得新增事实。
2. 不得删除 pending/warning/requires_user_review 的语义。
3. 不得改变仓库排名、分数、证据标签、复现边界。
4. 不得删除证据引用。
5. 不得把待确认结论写成确定结论。
6. 无 run_log 时不得声称复现成功、实测通过、实际运行成功。
7. 如果 confidence_level=low，不得输出强推荐。
8. 不输出证据附录（evidence appendix）、完整评分矩阵、raw evidence id、source_uri。
9. 可保留 E01/E02 这种短证据编号，但建议减少使用。
10. 输出完整 Markdown，不要输出 JSON。

executive_summary:
{executive_summary or ''}

pending_warnings:
{warnings_text or '（无）'}
{synthesis_text}
{quality_text}
sections:
{section_text}
""".strip()
