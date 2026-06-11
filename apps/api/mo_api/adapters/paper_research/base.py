"""PaperResearch 适配器抽象（MO_Backend §7.3 / §7.4）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class PaperContext(BaseModel):
    """paper-qa 单条检索上下文。"""

    text: str
    source_name: str
    locator: str | None = None


class PaperAnswer(BaseModel):
    answer: str = ""
    contexts: list[PaperContext] = Field(default_factory=list)


class WebSource(BaseModel):
    url: str
    summary: str = ""


class WebResearchResult(BaseModel):
    report: str = ""
    sources: list[WebSource] = Field(default_factory=list)


class PaperResearchError(Exception):
    """论文调研失败（脱敏消息）。"""


class PaperResearchAdapter(ABC):
    @abstractmethod
    async def query_papers(
        self,
        doc_paths: list[str],
        question: str,
        *,
        task_id: str,
    ) -> PaperAnswer:
        """对给定文档路径执行 paper-qa 查询。"""


class WebResearchAdapter(ABC):
    @abstractmethod
    async def research(
        self,
        query: str,
        *,
        report_type: str = "research_report",
    ) -> WebResearchResult:
        """联网背景调研（受 allow_web_search 门控）。"""
