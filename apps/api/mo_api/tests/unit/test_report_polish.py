"""Report polish service tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mo_api.models.report import ReportSection
from mo_api.services.report_polish import (
    FinalReportPolisher,
    SectionDraft,
    SectionPolisher,
    extract_report_markdown,
    has_required_report_sections,
    parse_jsonish,
)


def test_parse_jsonish_accepts_fenced_json() -> None:
    data = parse_jsonish('```json\n{"reader_markdown":"ok"}\n```')
    assert data["reader_markdown"] == "ok"


def test_extract_report_markdown_strips_chatty_fence() -> None:
    raw = "好的，这是报告。\n\n```markdown\n# Title\n\n## Section\nbody\n```"
    assert extract_report_markdown(raw) == "# Title\n\n## Section\nbody"


def test_has_required_report_sections_requires_numbered_sections() -> None:
    full = "# R\n\n" + "\n".join(f"## {i}. Section\nbody" for i in range(1, 14))
    partial = "# R\n\n## 1. Section\nbody"
    assert has_required_report_sections(full) is True
    assert has_required_report_sections(partial) is False


@pytest.mark.asyncio
async def test_section_polisher_parses_json() -> None:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(
        return_value=(
            '{"summary":"摘要","reader_markdown":"润色后的正文","warnings":["w1"]}'
        )
    )
    draft = SectionDraft(
        key="repo_overview",
        title="仓库概览",
        structured_markdown="原始正文",
    )

    polished = await SectionPolisher(gateway).polish(draft, output_language="zh")

    assert polished.reader_markdown == "润色后的正文"
    assert polished.summary == "摘要"
    assert polished.warnings == ["w1"]
    assert polished.polish_status == "polished"


@pytest.mark.asyncio
async def test_section_polisher_falls_back_on_failure() -> None:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(side_effect=RuntimeError("timeout"))
    draft = SectionDraft(
        key="technical_route",
        title="技术路线",
        structured_markdown="结构化正文",
    )

    polished = await SectionPolisher(gateway).polish(draft, output_language="zh")

    assert polished.reader_markdown == "结构化正文"
    assert polished.polish_status == "fallback"
    assert polished.warnings


@pytest.mark.asyncio
async def test_final_report_polisher_falls_back_on_failure() -> None:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(side_effect=RuntimeError("timeout"))
    section = ReportSection(
        key="repo_overview",
        title="仓库概览",
        markdown="正文",
    )

    markdown = await FinalReportPolisher(gateway).polish_report(
        executive_summary="摘要",
        sections=[section],
        pending_warnings=[],
        output_language="zh",
        fallback_markdown="fallback markdown",
    )

    assert markdown == "fallback markdown"


@pytest.mark.asyncio
async def test_final_report_polisher_rejects_non_report_markdown() -> None:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(return_value='{"reader_markdown":"not a report"}')
    section = ReportSection(
        key="repo_overview",
        title="仓库概览",
        markdown="正文",
    )

    markdown = await FinalReportPolisher(gateway).polish_report(
        executive_summary="摘要",
        sections=[section],
        pending_warnings=[],
        output_language="zh",
        fallback_markdown="fallback markdown",
    )

    assert markdown == "fallback markdown"
