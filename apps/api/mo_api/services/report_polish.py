"""报告章节与全文润色服务。

润色层只负责表达编辑，不拥有 claim/evidence/score/ranking 的事实控制权。
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

logger = logging.getLogger("mo_api.report_polish")


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
    return len(re.findall(r"(?m)^##\s+\d+\.", markdown)) >= 13


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
            reader_markdown=draft.structured_markdown,
            summary=draft.summary,
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
    ) -> str:
        profile = self.gateway.select(need_reasoning=True, long_context=True)
        prompt = build_final_report_polish_prompt(
            executive_summary=executive_summary,
            sections=sections,
            pending_warnings=pending_warnings,
            output_language=output_language,
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
            if not text or "## " not in text or not has_required_report_sections(text):
                logger.warning("final report polish returned non-report markdown")
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
) -> str:
    lang_instruction = "请用中文。" if output_language == "zh" else "Use English."
    section_text = "\n\n".join(
        f"## {section.title}\n{section.markdown[:5000]}" for section in sections
    )
    warnings_text = "\n".join(f"- {warning}" for warning in pending_warnings)
    return f"""
你是 MO 最终报告编辑器。{lang_instruction}

你会收到已经完成事实校验和证据标注的章节文本。你只能做总编：优化摘要、改善章节衔接、合并重复表达、统一语气。

硬性规则：
1. 不得新增事实。
2. 不得删除 pending/warning/requires_user_review。
3. 不得改变仓库排名、分数、证据标签、复现边界。
4. 不得删除证据引用。
5. 不得把待确认结论写成确定结论。
6. 无 run_log 时不得声称复现成功。
7. 保留章节标题。
8. 输出完整 Markdown，不要输出 JSON。

executive_summary:
{executive_summary or ''}

pending_warnings:
{warnings_text or '（无）'}

sections:
{section_text}
""".strip()
