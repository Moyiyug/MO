"""RepoDiscovery 发现流程单测（F-015）。

直接测试 discover_candidates（注入 mock adapter/gateway），不触发真实联网/模型。
"""

from __future__ import annotations

import pytest

from mo_api.adapters.repo_discovery.base import (
    RepoDiscoveryAdapter,
    RepoDiscoveryError,
)
from mo_api.models.repo_discovery import RepoCandidate
from mo_api.workflows.nodes import repo_discovery as node


class _FakeProfile:
    id = "fake"


class _FakeGateway:
    def select(self, **kwargs):
        return _FakeProfile()

    async def complete(self, profile, messages, **kwargs):
        content = messages[0]["content"]
        if "search queries" in content:
            return '["llm agent framework", "rag pipeline"]'
        if "relevance" in content.lower():
            return (
                '[{"index":0,"score":0.95,"reason":"strong match"},'
                '{"index":1,"score":0.40,"reason":"weak match"}]'
            )
        return "[]"


class _FakeAdapter(RepoDiscoveryAdapter):
    def __init__(self, candidates=None, *, error: bool = False) -> None:
        self._candidates = candidates or []
        self._error = error
        self.calls: list[list[str]] = []

    async def search(self, queries, *, per_query=5, limit=15):
        self.calls.append(list(queries))
        if self._error:
            raise RepoDiscoveryError("boom")
        return list(self._candidates)


def _candidate(name: str, stars: int) -> RepoCandidate:
    return RepoCandidate(
        repo_url=f"https://github.com/{name}",
        repo_name=name,
        stars=stars,
        discovered_by="github_search",
    )


@pytest.fixture
def stub_settings(monkeypatch):
    settings = type(
        "S",
        (),
        {
            "repo_discovery_enabled": True,
            "repo_discovery_per_query": 5,
            "repo_discovery_max_candidates": 15,
        },
    )()
    monkeypatch.setattr(node, "get_settings", lambda: settings)
    return settings


async def test_discover_ranks_by_relevance(stub_settings) -> None:
    adapter = _FakeAdapter([_candidate("o/a", 10), _candidate("o/b", 999)])
    gateway = _FakeGateway()

    candidates, note = await node.discover_candidates(
        "compare llm agent frameworks", [], adapter=adapter, gateway=gateway
    )

    assert note is None
    assert [c.repo_name for c in candidates] == ["o/a", "o/b"]
    assert candidates[0].relevance_score == 0.95
    assert candidates[1].relevance_score == 0.40
    assert adapter.calls  # 调用了搜索


async def test_seeds_marked_selected_and_first(stub_settings) -> None:
    adapter = _FakeAdapter([_candidate("o/found", 50)])
    candidates, _ = await node.discover_candidates(
        "goal",
        ["https://github.com/o/seed"],
        adapter=adapter,
        gateway=_FakeGateway(),
    )

    by_url = {c.repo_url: c for c in candidates}
    seed = by_url["https://github.com/o/seed"]
    assert seed.selected is True
    assert seed.discovered_by == "user_seed"
    # 已选项排在最前
    assert candidates[0].selected is True


async def test_adapter_error_degrades_to_seeds(stub_settings) -> None:
    adapter = _FakeAdapter(error=True)
    candidates, note = await node.discover_candidates(
        "goal",
        ["https://github.com/o/seed"],
        adapter=adapter,
        gateway=_FakeGateway(),
    )

    assert note is not None and "降级" in note
    assert [c.repo_name for c in candidates] == ["o/seed"]
    assert candidates[0].discovered_by == "user_seed"


async def test_discovery_disabled_uses_seeds_only(monkeypatch) -> None:
    settings = type(
        "S",
        (),
        {
            "repo_discovery_enabled": False,
            "repo_discovery_per_query": 5,
            "repo_discovery_max_candidates": 15,
        },
    )()
    monkeypatch.setattr(node, "get_settings", lambda: settings)

    adapter = _FakeAdapter([_candidate("o/should-not-appear", 100)])
    candidates, note = await node.discover_candidates(
        "goal",
        ["https://github.com/o/seed"],
        adapter=adapter,
        gateway=_FakeGateway(),
    )

    assert note is not None and "已禁用" in note
    assert [c.repo_name for c in candidates] == ["o/seed"]
    assert adapter.calls == []  # 未触发搜索


async def test_no_candidates_returns_note(stub_settings) -> None:
    adapter = _FakeAdapter([])
    candidates, note = await node.discover_candidates(
        "goal", [], adapter=adapter, gateway=_FakeGateway()
    )
    assert candidates == []
    assert note is not None


async def test_rerank_falls_back_to_stars_when_llm_returns_bad_json(
    stub_settings,
) -> None:
    """LLM 返回非法 JSON 时 _rerank 应回退到 stars 归一化排序。（F-015）"""
    adapter = _FakeAdapter([
        _candidate("popular", stars=1000),
        _candidate("niche", stars=10),
    ])

    class _BadJsonGateway:
        def select(self, **kwargs):
            return _FakeProfile()

        async def complete(self, profile, messages, **kwargs):
            content = messages[0]["content"]
            if "search queries" in content:
                return '["test query"]'
            # _rerank 收到非 JSON 文本 → 应触发 _stars_fallback
            return "this is not valid json at all"

    candidates, note = await node.discover_candidates(
        "goal", [], adapter=adapter, gateway=_BadJsonGateway()
    )

    # 回退到 stars 排序：popular(1000) 排第一，niche(10) 排第二
    assert len(candidates) == 2
    assert candidates[0].repo_name == "popular"
    assert candidates[1].repo_name == "niche"
    # 回退时 relevance_reason 应包含 "stars 热度"
    assert "stars 热度" in candidates[0].relevance_reason
    assert note is None
