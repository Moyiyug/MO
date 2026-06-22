"""深度研究报告通用断言工具（PRD F5 / F7 验收）。

使用方式：
    from mo_api.tests.helpers.report_assertions import assert_deep_research_reader
    assert_deep_research_reader(report.markdown)
"""

from __future__ import annotations

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


def assert_deep_research_reader(markdown: str) -> None:
    """验收深度研究报告 reader 必备条件。

    必须包含：
      - # MO 深度调研报告 标题
      - 结论/判断 相关内容
      - 不确定/边界 相关内容
      - 下一步/验证 相关内容

    必须不包含：
      - 所有 FORBIDDEN_READER_TERMS
      - "复现成功"（无 run_log 时不得出现）
      - "实测通过"（无 run_log 时不得出现）
    """
    assert "# MO 深度调研报告" in markdown
    assert "结论" in markdown or "判断" in markdown
    assert "不确定" in markdown or "边界" in markdown
    assert "下一步" in markdown or "验证" in markdown
    for term in FORBIDDEN_READER_TERMS:
        assert term not in markdown, f"forbidden term found in reader: {term}"
    assert "复现成功" not in markdown, (
        "reader must not claim repro success without run_log"
    )
    assert "实测通过" not in markdown, (
        "reader must not claim actual test pass without run_log"
    )
