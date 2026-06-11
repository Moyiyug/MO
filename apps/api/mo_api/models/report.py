"""报告领域模型（PRD F-011）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .evidence import ReportClaim

# PRD F-011 规定的 13 段报告章节 key（顺序固定）
REPORT_SECTION_KEYS: list[str] = [
    "task_background",
    "user_boundaries",
    "approved_plan",
    "execution_summary",
    "repo_overview",
    "paper_supplement",
    "technical_route",
    "comparison_matrix",
    "reproducibility",
    "risks",
    "recommendation",
    "next_steps",
    "evidence_references",
]

REPORT_SECTION_TITLES: dict[str, str] = {
    "task_background": "1. 任务背景",
    "user_boundaries": "2. 用户确认边界",
    "approved_plan": "3. 已批准计划",
    "execution_summary": "4. 执行摘要",
    "repo_overview": "5. 仓库概览",
    "paper_supplement": "6. 论文/上下文补充",
    "technical_route": "7. 技术路线分析",
    "comparison_matrix": "8. 对比矩阵",
    "reproducibility": "9. 复现性分析",
    "risks": "10. 风险与不确定性",
    "recommendation": "11. 推荐与场景",
    "next_steps": "12. 后续步骤",
    "next_steps_en": "12. Next Steps",
    "evidence_references": "13. 证据与引用",
}


class ReportSection(BaseModel):
    """单段报告内容。"""

    key: str
    title: str
    markdown: str
    claims: list[ReportClaim] = Field(default_factory=list)
    is_pending: bool = False


class Report(BaseModel):
    """完整调研报告（PRD F-011）。"""

    id: str
    task_id: str
    sections: list[ReportSection]
    pending_warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
    markdown: str
