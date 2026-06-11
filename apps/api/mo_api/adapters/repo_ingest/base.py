"""RepoIngest 适配器抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...models.repo import RepoDigest


class RepoIngestAdapter(ABC):
    @abstractmethod
    async def ingest(self, repo_url: str, *, token: str | None = None) -> RepoDigest:
        """拉取并解析仓库，返回 RepoDigest。"""
