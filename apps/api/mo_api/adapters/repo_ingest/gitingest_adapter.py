"""gitingest 仓库摄取适配器（MO_Backend §7.2）。"""

from __future__ import annotations

import os
import re

from ...config import get_settings
from ...models.repo import RepoDigest
from .base import RepoIngestAdapter


class RepoIngestError(Exception):
    """仓库摄取失败（脱敏消息）。"""


def _sanitize_error(message: str, token: str | None = None) -> str:
    text = message or "repo ingest failed"
    if token:
        text = text.replace(token, "[REDACTED]")
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


class GitingestAdapter(RepoIngestAdapter):
    def __init__(self) -> None:
        settings = get_settings()
        self._max_bytes = settings.repo_ingest_max_bytes
        patterns = settings.repo_ingest_exclude_patterns
        self._exclude_patterns = [p.strip() for p in patterns.split(",") if p.strip()]
        include_raw = getattr(settings, "repo_ingest_include_patterns", "")
        self._include_patterns = (
            [p.strip() for p in include_raw.split(",") if p.strip()]
            if include_raw
            else []
        )

    async def ingest(self, repo_url: str, *, token: str | None = None) -> RepoDigest:
        # 读取 GITHUB_TOKEN（参数优先，其次 env）
        effective_token = token
        if effective_token is None:
            effective_token = os.environ.get("GITHUB_TOKEN", "").strip() or None

        try:
            from gitingest import ingest_async
        except ImportError as exc:
            raise RepoIngestError(
                "gitingest is not installed; add gitingest to requirements"
            ) from exc

        kwargs: dict = {
            "exclude_patterns": self._exclude_patterns,
        }
        if self._include_patterns:
            kwargs["include_patterns"] = self._include_patterns
        if effective_token:
            kwargs["token"] = effective_token

        try:
            summary, tree, content = await ingest_async(repo_url, **kwargs)
        except Exception as exc:
            raise RepoIngestError(
                _sanitize_error(str(exc), effective_token)
            ) from exc

        total_size = sum(len(v.encode("utf-8", errors="ignore")) for v in content.values())
        if total_size > self._max_bytes:
            raise RepoIngestError(
                f"repository content exceeds max size ({self._max_bytes} bytes)"
            )

        return RepoDigest(
            summary=summary or "",
            tree=tree or "",
            content=dict(content or {}),
            source_uri=repo_url,
        )
