"""RepoDiscovery 适配器抽象基类（PRD F-015）。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...models.repo_discovery import RepoCandidate


class RepoDiscoveryError(Exception):
    """仓库发现失败（脱敏，不含 token/堆栈）。"""


class RepoDiscoveryAdapter(ABC):
    @abstractmethod
    async def search(
        self,
        queries: list[str],
        *,
        per_query: int = 5,
        limit: int = 15,
    ) -> list[RepoCandidate]:
        """按关键词查询，返回去重后的候选仓库列表（按 stars 降序）。"""
