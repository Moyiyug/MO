"""GitHub Search API 适配器（PRD F-015）。

只读公开仓库元数据（名称/stars/语言/简介/topics），不克隆、不下载，低成本。
token 仅从环境变量读取（config 只存变量名），失败包成 MO 错误对象并脱敏。
"""

from __future__ import annotations

import os
import re

import httpx

from ...config import get_settings
from ...models.repo_discovery import RepoCandidate
from .base import RepoDiscoveryAdapter, RepoDiscoveryError

_TOKEN_RE = re.compile(r"(gh[a-z]_[A-Za-z0-9]+)")


def _sanitize_error(message: str) -> str:
    text = message or "repo discovery failed"
    text = _TOKEN_RE.sub("[REDACTED]", text)
    text = re.sub(r"(?i)(token|authorization|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


def _to_candidate(item: dict) -> RepoCandidate | None:
    repo_url = item.get("html_url")
    full_name = item.get("full_name")
    if not repo_url or not full_name:
        return None
    raw_desc = item.get("description")
    description: str | None = None
    if raw_desc:
        text = str(raw_desc).strip()
        if text:
            description = text[:240] + ("…" if len(text) > 240 else "")

    return RepoCandidate(
        repo_url=str(repo_url),
        repo_name=str(full_name),
        description=description,
        stars=int(item.get("stargazers_count") or 0),
        language=item.get("language"),
        pushed_at=item.get("pushed_at"),
        topics=list(item.get("topics") or []),
        discovered_by="github_search",
    )


class GitHubSearchAdapter(RepoDiscoveryAdapter):
    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.github_api_base_url).rstrip("/")
        self._token_env = settings.github_token_env
        self._timeout = float(settings.repo_discovery_timeout_seconds)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get(self._token_env, "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def search(
        self,
        queries: list[str],
        *,
        per_query: int = 5,
        limit: int = 15,
    ) -> list[RepoCandidate]:
        cleaned = [q.strip() for q in queries if q and q.strip()]
        if not cleaned:
            return []

        deduped: dict[str, RepoCandidate] = {}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                for query in cleaned:
                    resp = await client.get(
                        f"{self._base_url}/search/repositories",
                        params={
                            "q": query,
                            "sort": "stars",
                            "order": "desc",
                            "per_page": max(1, min(per_query, 50)),
                        },
                        headers=self._headers(),
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    for item in data.get("items", []):
                        candidate = _to_candidate(item)
                        if candidate is None:
                            continue
                        # 去重：保留 stars 更高者
                        existing = deduped.get(candidate.repo_url)
                        if existing is None or candidate.stars > existing.stars:
                            deduped[candidate.repo_url] = candidate
        except httpx.HTTPError as exc:
            raise RepoDiscoveryError(_sanitize_error(str(exc))) from exc
        except Exception as exc:  # noqa: BLE001 - 统一包成 MO 错误对象
            raise RepoDiscoveryError(_sanitize_error(str(exc))) from exc

        ranked = sorted(deduped.values(), key=lambda c: c.stars, reverse=True)
        return ranked[:limit]
