"""gpt-researcher 适配器（MO_Backend §7.4）。"""

from __future__ import annotations

import re

from .base import PaperResearchError, WebResearchAdapter, WebResearchResult, WebSource


def _sanitize_error(message: str) -> str:
    text = message or "web research failed"
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


class GPTResearcherAdapter(WebResearchAdapter):
    async def research(
        self,
        query: str,
        *,
        report_type: str = "research_report",
    ) -> WebResearchResult:
        try:
            from gpt_researcher import GPTResearcher
        except ImportError as exc:
            raise PaperResearchError(
                "gpt-researcher is not installed; add gpt-researcher to requirements"
            ) from exc

        try:
            researcher = GPTResearcher(query=query, report_type=report_type)
            await researcher.conduct_research()
            report = await researcher.write_report()
            source_urls = []
            if hasattr(researcher, "get_source_urls"):
                source_urls = researcher.get_source_urls() or []
        except Exception as exc:
            raise PaperResearchError(_sanitize_error(str(exc))) from exc

        sources = [
            WebSource(url=str(url), summary=f"Web source: {url}")
            for url in source_urls[:20]
        ]
        sanitized_report = _sanitize_error(str(report)[:8000])
        return WebResearchResult(report=sanitized_report, sources=sources)
