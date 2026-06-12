"""RepoDiscovery 适配器（PRD F-015）。"""

from __future__ import annotations

from functools import lru_cache

from .base import RepoDiscoveryAdapter, RepoDiscoveryError
from .github_search_adapter import GitHubSearchAdapter

__all__ = [
    "RepoDiscoveryAdapter",
    "RepoDiscoveryError",
    "GitHubSearchAdapter",
    "get_repo_discovery_adapter",
]


@lru_cache
def get_repo_discovery_adapter() -> RepoDiscoveryAdapter:
    """默认发现适配器（GitHub Search API）。测试可 monkeypatch 调用点。"""
    return GitHubSearchAdapter()
