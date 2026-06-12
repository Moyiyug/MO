"""GitHubSearchAdapter 单测（F-015）。

全部用 respx mock httpx，禁止真实联网。
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mo_api.adapters.repo_discovery import GitHubSearchAdapter
from mo_api.adapters.repo_discovery.base import RepoDiscoveryError

_BASE = "https://api.github.com"


def _item(full_name: str, stars: int, *, lang: str = "Python") -> dict:
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": f"desc of {full_name}",
        "stargazers_count": stars,
        "language": lang,
        "pushed_at": "2026-01-01T00:00:00Z",
        "topics": ["llm", "agent"],
    }


@respx.mock
async def test_search_maps_items_sorted_by_stars() -> None:
    respx.get(f"{_BASE}/search/repositories").mock(
        return_value=httpx.Response(
            200,
            json={"items": [_item("a/low", 10), _item("b/high", 100)]},
        )
    )
    adapter = GitHubSearchAdapter()
    out = await adapter.search(["llm agent"], per_query=5, limit=10)

    assert [c.repo_name for c in out] == ["b/high", "a/low"]
    assert out[0].stars == 100
    assert out[0].repo_url == "https://github.com/b/high"
    assert out[0].language == "Python"
    assert out[0].discovered_by == "github_search"
    assert "llm" in out[0].topics


@respx.mock
async def test_search_dedupes_keeping_higher_stars() -> None:
    respx.get(f"{_BASE}/search/repositories").mock(
        side_effect=[
            httpx.Response(200, json={"items": [_item("x/dup", 5)]}),
            httpx.Response(200, json={"items": [_item("x/dup", 50)]}),
        ]
    )
    adapter = GitHubSearchAdapter()
    out = await adapter.search(["q1", "q2"], per_query=5, limit=10)

    assert len(out) == 1
    assert out[0].stars == 50


@respx.mock
async def test_search_respects_limit() -> None:
    items = [_item(f"o/r{i}", i) for i in range(20)]
    respx.get(f"{_BASE}/search/repositories").mock(
        return_value=httpx.Response(200, json={"items": items})
    )
    adapter = GitHubSearchAdapter()
    out = await adapter.search(["q"], per_query=20, limit=5)
    assert len(out) == 5


async def test_search_empty_queries_returns_empty() -> None:
    adapter = GitHubSearchAdapter()
    assert await adapter.search(["", "  "]) == []


@respx.mock
async def test_search_http_error_wrapped() -> None:
    respx.get(f"{_BASE}/search/repositories").mock(
        return_value=httpx.Response(403, json={"message": "rate limited"})
    )
    adapter = GitHubSearchAdapter()
    with pytest.raises(RepoDiscoveryError):
        await adapter.search(["q"])


@respx.mock
async def test_search_sends_auth_header_when_token_present(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secrettoken123")
    route = respx.get(f"{_BASE}/search/repositories").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    adapter = GitHubSearchAdapter()
    await adapter.search(["q"])

    assert route.called
    auth = route.calls.last.request.headers.get("Authorization")
    assert auth == "Bearer ghp_secrettoken123"
