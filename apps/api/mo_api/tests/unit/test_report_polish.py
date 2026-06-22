"""Report polish service tests — 包含 Phase 3 深度研究报告校验、禁词、fallback。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mo_api.models.report import ReportSection
from mo_api.models.research_synthesis import ResearchQuality, ResearchSynthesis
from mo_api.services.report_polish import (
    FORBIDDEN_READER_TERMS,
    SAFE_SECTION_FALLBACK_ZH,
    FinalReportPolisher,
    SectionDraft,
    SectionPolisher,
    build_safe_deep_research_fallback,
    extract_report_markdown,
    has_required_report_sections,
    parse_jsonish,
    validate_deep_research_markdown,
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

    assert polished.reader_markdown == SAFE_SECTION_FALLBACK_ZH
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


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: validate_deep_research_markdown
# ═══════════════════════════════════════════════════════════════════════════


# 满足 800 字符长度要求的共享有效深度研究报告模板
_VALID_DEEP_RESEARCH_BODY = (
    "基于对候选仓库的深入分析、代码结构解读、PaperQA 资料调研"
    "以及多维度对比矩阵的系统评估，本次研究的核心判断是："
    "候选方案在技术路线、工程成熟度和适用场景上各有侧重，"
    "暂无可无脑推荐的单一最优方案。用户需结合具体场景需求和"
    "资源条件做出最终选型判断，本报告仅提供基于当前证据的综合分析。"
    "从架构层面看，各方案在核心抽象的设计上存在本质差异，"
    "这决定了它们在不同类型项目中的适用性。"
    "从工程角度看，文档完整度、测试覆盖率、依赖管理策略"
    "以及社区响应速度都是影响实际使用体验的关键因素。"
    "在复现性方面，虽然缺少实际运行日志验证，但静态评估"
    "已经揭示了安装文档质量、依赖声明完整性和示例代码可用性"
    "等方面的差异。用户在进行最终选型时，应充分考虑自身团队"
    "的技术栈偏好、项目的时间约束以及对长期维护的要求。"
    "根据对比矩阵的评估结果，各方案在不同维度的得分差异"
    "反映了它们在设计目标和工程实践上的不同侧重。"
    "有些方案更注重灵活性和可扩展性，适合需要深度定制的场景；"
    "有些方案则强调开箱即用和文档完整性，适合快速原型验证。"
    "此外，许可证类型也是选型中不可忽视的因素，尤其在商业项目中。"
    "建议在实际采用前，对排名靠前的方案进行概念验证，"
    "通过最小可行实现来检验方案在具体业务场景中的表现。"
    "同时持续关注相关社区的版本更新和安全公告。"
)


def test_validate_deep_research_markdown_passes_valid_report() -> None:
    markdown = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        + _VALID_DEEP_RESEARCH_BODY + "\n\n"
        "## 为什么是这个判断\n\n"
        "此判断基于仓库分析、代码结构解读和资料调研。"
        "虽然静态评估提供了较为全面的分析基础，但由于缺少实际运行日志，"
        "复现相关的结论仅属于静态推断，不应被理解为实测验证结果。"
        "每个维度的评估都有对应的证据支持，证据链可追溯到具体的"
        "仓库文件、论文摘要或网络资料。在审阅时建议重点关注"
        "标记为 pending 的结论项以及弱证据支持的推断。\n\n"
        "## 候选方案如何理解\n\n"
        "各候选方案在核心抽象和技术栈选择上存在明显差异。"
        "通过仓库档案分析，每个方案都有其独特的设计哲学和适用边界。"
        "不存在放之四海皆准的统一方案，需要根据具体需求匹配。\n\n"
        "## 关键权衡\n\n"
        "在选择方案时需要重点关注工程成熟度与前沿创新的平衡、"
        "文档完整度与社区活跃度的关系、以及复现难易度与技术复杂度的矛盾。"
        "没有完美的方案，只有更适合当前需求的方案。\n\n"
        "## 不确定性与边界\n\n"
        "本次研究存在以下不确定性和边界：复现评估均为静态分析，"
        "未经实际运行验证；部分证据为弱证据或模型推断，需要人工审核确认；"
        "对比矩阵的权重设置可能影响最终排名，建议用户根据自身场景调整。"
        "调研无法覆盖所有边缘场景和最新版本变化，结论具有时效性限制。\n\n"
        "## 下一步验证路线\n\n"
        "建议对排名靠前的仓库进行实际安装和冒烟测试验证；"
        "补充弱证据相关的文档和代码验证；"
        "结合具体业务场景进行概念验证开发；"
        "持续关注相关仓库的版本更新和社区动态。\n"
    )
    errors = validate_deep_research_markdown(markdown)
    assert errors == []


def test_validate_deep_research_markdown_rejects_missing_title() -> None:
    errors = validate_deep_research_markdown("no title here\n\n## 结论先行\nbody")
    assert any("missing title" in e for e in errors)


def test_validate_deep_research_markdown_rejects_too_short() -> None:
    errors = validate_deep_research_markdown("# Title\n\nshort")
    assert any("too short" in e for e in errors)


def test_validate_deep_research_markdown_rejects_missing_conclusion() -> None:
    # 故意避免使用 结论/判断/Conclusion/Finding 关键词，
    # 长度需 >800 字符。正文只使用"评估""分析""观察"等词。
    body = (
        "基于对候选仓库的深入分析、代码结构解读、PaperQA 资料调研"
        "以及多维度对比矩阵的系统评估，本次研究的核心观察是："
        "候选方案在技术路线、工程成熟度和适用场景上各有侧重，"
        "暂无可无脑推荐的单一最优方案。用户需结合具体场景需求和"
        "资源条件做出最终选型评估，本报告仅提供基于当前证据的综合分析。"
        "从架构层面看，各方案在核心抽象的设计上存在本质差异，"
        "这决定了它们在不同类型项目中的适用性。"
        "从工程角度看，文档完整度、测试覆盖率、依赖管理策略"
        "以及社区响应速度都是影响实际使用体验的关键因素。"
        "在复现性方面，虽然缺少实际运行日志验证，但静态评估"
        "已经揭示了安装文档质量、依赖声明完整性和示例代码可用性"
        "等方面的差异。用户在进行最终选型时，应充分考虑自身团队"
        "的技术栈偏好、项目的时间约束以及对长期维护的要求。"
        "根据对比矩阵的评估结果，各方案在不同维度的得分差异"
        "反映了它们在设计目标和工程实践上的不同侧重。"
        "有些方案更注重灵活性和可扩展性，适合需要深度定制的场景；"
        "有些方案则强调开箱即用和文档完整性，适合快速原型验证。"
        "此外，许可证类型也是选型中不可忽视的因素，尤其在商业项目中。"
        "建议在实际采用前，对排名靠前的方案进行概念验证，"
        "通过最小可行实现来检验方案在具体业务场景中的表现。"
        "同时持续关注相关社区的版本更新和安全公告。"
    )
    markdown = (
        "# MO 深度调研报告\n\n"
        "## 为什么如此评估\n\n"
        + body + "\n\n"
        "## 候选方案差异分析\n\n"
        "各方案有不同的设计哲学和适用场景。"
        "分析过程文字，但没有明确的总结性关键词。综合来看，"
        "没有一个方案在所有维度上都占据绝对优势，"
        "用户需要根据自身的具体需求和技术背景做出选择。"
        "后续建议对重点方案进行实际运行验证，以弥补静态分析的不足。"
        "另外还需要关注各个仓库的许可证兼容性以及长期维护前景。\n\n"
        "## 关键权衡\n\n"
        "工程成熟度与前沿创新的平衡是核心权衡点。\n\n"
        "## 不确定性与边界\n\n"
        "静态分析有其内在局限性，部分证据强度不足以支撑确定评估。\n\n"
        "## 下一步验证路线\n\n"
        "建议对重点仓库进行安装测试和概念验证。验证步骤包括环境搭建、"
        "依赖安装、示例运行和性能测试，需要足够时间来完成这些验证工作。\n"
    )
    errors = validate_deep_research_markdown(markdown)
    assert any("conclusion" in e for e in errors)


def test_validate_deep_research_markdown_rejects_missing_uncertainty() -> None:
    markdown = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        "基于分析，本次研究得到的核心判断是：各方案各有侧重。\n\n"
        "## 为什么是这个判断\n\n"
        "此判断基于仓库分析、代码解读和资料调研。每个方案都有其独特优势。\n\n"
        "## 候选方案如何理解\n\n"
        "各方案有不同的设计哲学和适用场景。\n\n"
        "## 关键权衡\n\n"
        "工程成熟度与前沿创新的平衡是核心权衡点。\n\n"
        "## 下一步验证路线\n\n"
        "建议对重点仓库进行安装测试和概念验证。验证步骤包括环境搭建、"
        "依赖安装、示例运行和性能测试，需要足够时间来完成这些验证工作。"
    )
    errors = validate_deep_research_markdown(markdown)
    assert any("uncertainty" in e for e in errors)


def test_validate_deep_research_markdown_rejects_forbidden_terms() -> None:
    markdown = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        "核心判断：各方案各有侧重。RepoCard 显示相关仓库的详细分析结果，"
        "通过 source_uri 可以追溯到原始资料。model_inference 给出的推断需要"
        "结合 static_reproducibility_assessment 的结果来评估可靠性。"
        "部分 LLM 未返回有效输出，需要人工补充。score=0.85 表示该方案在"
        "当前权重下排名最高。docs= 和 deps= 字段提供了基础信息。"
        "entrypoints= 指示了代码入口。M10 sandbox 在测试中可用。"
        "ReportSectionSeed 中的 structured_markdown 提供了结构化数据。\n\n"
        "## 为什么是这个判断\n\n"
        "基于 raw evidence id 分析得出的结论。\n\n"
        "## 候选方案如何理解\n\n"
        "各方案存在差异。\n\n"
        "## 关键权衡\n\n"
        "需要权衡多个因素。\n\n"
        "## 不确定性与边界\n\n"
        "存在的限制包括静态分析的局限性、模型推断的不确定性。\n\n"
        "## 下一步验证路线\n\n"
        "建议进行实际验证测试。\n"
    )
    errors = validate_deep_research_markdown(markdown)
    forbidden = [
        "RepoCard", "model_inference", "source_uri", "raw evidence id",
        "static_reproducibility_assessment", "LLM 未返回", "score=",
        "docs=", "deps=", "entrypoints=", "M10 sandbox",
        "ReportSectionSeed", "structured_markdown",
    ]
    for term in forbidden:
        assert any(term in e for e in errors), f"should reject: {term}"


def test_validate_deep_research_markdown_rejects_evidence_appendix() -> None:
    markdown = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        "基于分析的核心判断：各方案各有侧重。\n\n"
        "## 为什么是这个判断\n\n"
        "此判断基于仓库分析、代码解读和资料调研。\n\n"
        "## 候选方案如何理解\n\n"
        "各方案在核心设计和技术栈上有差异。\n\n"
        "## 关键权衡\n\n"
        "工程成熟度与创新的平衡。\n\n"
        "## 不确定性与边界\n\n"
        "静态分析的局限性是不可回避的边界。\n\n"
        "## 下一步验证路线\n\n"
        "进行实际安装和冒烟测试。\n\n"
        "## 13. 证据与引用\n\n"
        "evidence appendix content here"
    )
    errors = validate_deep_research_markdown(markdown)
    assert any("evidence appendix" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: SectionPolisher fallback 安全
# ═══════════════════════════════════════════════════════════════════════════


def test_section_polisher_fallback_does_not_expose_structured_markdown() -> None:
    """SectionPolisher._fallback 返回安全文案，不包含 structured_markdown 原文。"""
    gateway = MagicMock()
    draft = SectionDraft(
        key="task_background",
        title="任务背景",
        structured_markdown="原始结构化数据包含内部术语 RepoCard score=0.8",
    )

    # 直接调用 _fallback 验证安全文案
    fallback = SectionPolisher(gateway)._fallback(draft, "test reason")

    assert fallback.reader_markdown == SAFE_SECTION_FALLBACK_ZH
    # 具体术语不能泄漏到 reader
    assert "RepoCard" not in fallback.reader_markdown
    assert "score=0.8" not in fallback.reader_markdown
    assert "原始结构化数据包含" not in fallback.reader_markdown
    assert fallback.polish_status == "fallback"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: build_safe_deep_research_fallback
# ═══════════════════════════════════════════════════════════════════════════


def test_build_safe_deep_research_fallback_contains_required_sections() -> None:
    synthesis = ResearchSynthesis(
        thesis="本次研究核心判断：方案 A 更适合快速原型。",
        key_insights=["洞察1", "洞察2"],
        uncertainty=["部分证据较弱", "无 run_log"],
        next_questions=["运行冒烟测试", "验证安装步骤"],
    )
    quality = ResearchQuality(
        research_depth="medium",
        confidence_level="medium",
        limitations=["PaperQA 未产生有效综合回答。"],
    )
    pending = ["对比矩阵尚未完成"]

    fallback = build_safe_deep_research_fallback(
        synthesis=synthesis,
        quality=quality,
        pending_warnings=pending,
    )

    assert "# MO 深度调研报告" in fallback
    assert "## 结论先行" in fallback
    assert "方案 A 更适合快速原型" in fallback
    assert "## 为什么是这个判断" in fallback
    assert "## 候选方案如何理解" in fallback
    assert "## 关键权衡" in fallback
    assert "## 不确定性与边界" in fallback
    assert "## 下一步验证路线" in fallback
    assert "部分证据较弱" in fallback
    assert "无 run_log" in fallback
    assert "运行冒烟测试" in fallback
    assert "PaperQA" in fallback
    assert "对比矩阵尚未完成" in fallback


def test_build_safe_deep_research_fallback_without_synthesis() -> None:
    fallback = build_safe_deep_research_fallback(
        synthesis=None,
        quality=None,
        pending_warnings=[],
    )
    assert "# MO 深度调研报告" in fallback
    assert "本次研究综合结论生成失败" in fallback
    assert "## 不确定性与边界" in fallback
    assert "## 下一步验证路线" in fallback


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3: FinalReportPolisher 深度研究校验集成
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_final_report_polisher_rejects_forbidden_terms() -> None:
    """包含禁词的 markdown 应触发 validate_deep_research_markdown 失败 → fallback。"""
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(
        return_value=(
            "# MO 深度调研报告\n\n"
            "## 结论先行\n\nRepoCard source_uri score=0.8\n\n"
            "## 为什么是这个判断\n\n分析表明每个方案各有侧重点。\n\n"
            "## 候选方案如何理解\n\n方案差异明显。\n\n"
            "## 关键权衡\n\n需要权衡工程成熟度与创新。\n\n"
            "## 不确定性与边界\n\n静态分析的局限性。\n\n"
            "## 下一步验证路线\n\n进行实际测试。\n"
        )
    )
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
        fallback_markdown="safe fallback",
    )

    assert markdown == "safe fallback"


@pytest.mark.asyncio
async def test_final_report_polisher_accepts_valid_deep_research() -> None:
    """合法深度研究报告应通过校验并直接返回。"""
    valid = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        + _VALID_DEEP_RESEARCH_BODY + "\n\n"
        "## 为什么是这个判断\n\n"
        "此判断基于仓库分析、代码结构解读、PaperQA 资料调研"
        "以及多维度对比矩阵的系统评估。虽然静态评估提供了较为全面的"
        "分析基础，但由于缺少实际运行日志，复现相关的结论仅属于静态推断。\n\n"
        "## 候选方案如何理解\n\n"
        "各候选方案在核心抽象、技术栈选择和目标场景方面存在明显差异。"
        "通过仓库档案分析，每个方案都有其独特的设计哲学和适用边界。\n\n"
        "## 关键权衡\n\n"
        "在选择方案时需要重点关注工程成熟度与前沿创新的平衡、"
        "文档完整度与社区活跃度的关系、以及复现难易度与技术复杂度的矛盾。\n\n"
        "## 不确定性与边界\n\n"
        "本次研究存在以下不确定性和边界：复现评估均为静态分析，"
        "未经实际运行验证；部分证据为弱证据或模型推断，需要人工审核确认；"
        "对比矩阵的权重设置可能影响排名。\n\n"
        "## 下一步验证路线\n\n"
        "建议对排名靠前的仓库进行实际安装和冒烟测试验证；"
        "补充弱证据相关的文档和代码验证；结合具体业务场景进行概念验证开发。\n"
    )
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(return_value=valid)
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
        fallback_markdown="safe fallback",
    )

    # extract_report_markdown 会 trim 尾部空白，使用 rstrip 比对
    assert markdown == valid.rstrip()
    assert "## 结论先行" in markdown
    assert "## 不确定性与边界" in markdown


@pytest.mark.asyncio
async def test_final_report_polisher_with_synthesis_quality() -> None:
    """传入 research_synthesis 和 research_quality 参数不应报错。"""
    synthesis = ResearchSynthesis(
        thesis="核心判断",
        uncertainty=["不确定性"],
        next_questions=["验证1"],
    )
    quality = ResearchQuality(research_depth="medium", confidence_level="medium")

    valid = (
        "# MO 深度调研报告\n\n"
        "## 结论先行\n\n"
        + _VALID_DEEP_RESEARCH_BODY + "\n\n"
        "## 为什么是这个判断\n\n"
        "此判断基于仓库分析、代码结构解读和资料调研得出。"
        "每个方案都有其独特的设计哲学和适用边界，需要通过实际验证来确认。"
        "综合来看，没有一个方案在所有维度上都占据绝对优势。\n\n"
        "## 候选方案如何理解\n\n"
        "各候选方案在核心抽象、技术栈选择和目标场景方面存在明显差异。"
        "通过仓库档案分析，每个方案都有其独特的设计哲学和适用边界。\n\n"
        "## 关键权衡\n\n"
        "在选择方案时需要重点关注工程成熟度与前沿创新的平衡、"
        "文档完整度与社区活跃度的关系、以及复现难易度与技术复杂度的矛盾。"
        "没有完美的方案，只有更适合当前需求的方案。\n\n"
        "## 不确定性与边界\n\n"
        "本次研究存在以下不确定性和边界：复现评估均为静态分析，"
        "未经实际运行验证；部分证据为弱证据或模型推断，需要人工审核确认；"
        "对比矩阵的权重设置可能影响最终排名。\n\n"
        "## 下一步验证路线\n\n"
        "建议的后续验证步骤包括：对排名靠前的仓库进行实际安装和冒烟测试验证；"
        "补充弱证据相关的文档和代码验证；结合具体业务场景进行概念验证开发。\n"
    )
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(return_value=valid)
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
        fallback_markdown="safe fallback",
        research_synthesis=synthesis,
        research_quality=quality,
    )

    assert "## 结论先行" in markdown
    assert markdown == valid.rstrip()
