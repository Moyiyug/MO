"""仓库自动发现数据模型（PRD F-015 RepoDiscovery）。

用户给出研究目标后，MO 通过 GitHub Search API + LLM 发现高相关热门仓库，
产出 RepoCandidate 列表，在 PlanMode 中由用户确认后再进入克隆/调研（R-001/R-002）。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DiscoveredBy = Literal["github_search", "user_seed"]


class RepoCandidate(BaseModel):
    """候选仓库（发现结果或用户种子）。"""

    repo_url: str
    repo_name: str
    description: str | None = None
    stars: int = 0
    language: str | None = None
    pushed_at: str | None = None
    topics: list[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_reason: str = ""
    selected: bool = False
    discovered_by: DiscoveredBy = "github_search"


class RepoCandidateListResponse(BaseModel):
    """候选仓库列表响应。"""

    task_id: str
    candidates: list[RepoCandidate] = Field(default_factory=list)
    discovery_note: str | None = None


class RepoCandidateSelectRequest(BaseModel):
    """用户提交选中的候选仓库（写回 task.repo_urls）。"""

    selected_repo_urls: list[str] = Field(min_length=1, max_length=5)
