"""ResearchSynthesis / ResearchQuality / PaperQAAnswerRecord 模型。

PRD F4 / F8：研究综合层与质量评分模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PaperQAAnswerRecord(BaseModel):
    """单次 PaperQA 多问题查询的回答记录（PRD F1 / F2）。"""

    question: str
    answer: str = ""
    context_evidence_ids: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    failed: bool = False
    warning: str | None = None


class ResearchSynthesis(BaseModel):
    """研究综合结果（PRD F4）。

    聚合 PaperQA、Web、RepoCard、Comparison、Reproducibility 的材料，
    提炼 thesis、insights、tradeoffs、uncertainty、next questions。
    """

    thesis: str = ""
    key_insights: list[str] = Field(default_factory=list)
    repo_interpretations: dict[str, str] = Field(default_factory=dict)
    tradeoffs: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ResearchQuality(BaseModel):
    """研究质量评分（PRD F8）。

    基于确定性规则，不依赖 LLM。
    """

    research_depth: Literal["shallow", "medium", "deep"] = "shallow"
    confidence_level: Literal["low", "medium", "high"] = "low"
    evidence_coverage: float = 0.0
    limitations: list[str] = Field(default_factory=list)
    has_paperqa_answer: bool = False
    has_web_report: bool = False
    repo_card_count: int = 0
    has_comparison: bool = False
    has_reproducibility: bool = False
    weak_or_missing_evidence_count: int = 0
