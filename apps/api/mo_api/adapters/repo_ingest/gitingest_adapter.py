"""gitingest 仓库摄取适配器（MO_Backend §7.2）。"""

from __future__ import annotations

import os
import re

from ...config import get_settings
from ...models.repo import RepoDigest
from .base import RepoIngestAdapter


class RepoIngestError(Exception):
    """仓库摄取失败（脱敏消息）。"""


def _normalize_glob_pattern(pattern: str) -> str:
    """将 `.md` 规范为 `*.md`，避免白名单误配导致摄取为空。"""
    p = pattern.strip()
    if not p or "*" in p:
        return p
    if p.startswith("."):
        return f"*{p}"
    return p


_FILE_BLOCK_RE = re.compile(
    r"={40,}\s*\nFILE:\s*(.+?)\s*\n={40,}\s*\n",
    re.MULTILINE,
)


def _parse_gitingest_content(raw: str | dict[str, str]) -> dict[str, str]:
    """兼容 gitingest 新版（content 为拼接字符串）与旧版（path→text 字典）。"""
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}

    parts = _FILE_BLOCK_RE.split(raw)
    if len(parts) < 3:
        return {"_ingest.txt": raw.strip()}

    files: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        path = parts[i].strip()
        body = parts[i + 1].strip()
        if path:
            files[path] = body
        i += 2
    return files or {"_ingest.txt": raw.strip()}


def _format_ingest_error(exc: BaseException, token: str | None = None) -> str:
    msg = str(exc).strip()
    if not msg:
        # 无消息异常（如 NotImplementedError()）— 保留类型名加建议
        msg = (
            f"{type(exc).__name__}（无详细消息）。"
            "可能是底层依赖缺失（如 git 未安装）或网络不通。"
            "请确认：1) git 已安装且在 PATH 中；2) 可以正常访问 GitHub；"
            "3) DEEPSEEK_API_KEY 已配置（若模型调用需要）。"
        )
    return _sanitize_error(msg, token)


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
        self._exclude_patterns = [
            _normalize_glob_pattern(p)
            for p in patterns.split(",")
            if p.strip()
        ]
        include_raw = getattr(settings, "repo_ingest_include_patterns", "")
        self._include_patterns = (
            [
                _normalize_glob_pattern(p)
                for p in include_raw.split(",")
                if p.strip()
            ]
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
            "exclude_patterns": set(self._exclude_patterns),
        }
        if self._include_patterns:
            kwargs["include_patterns"] = set(self._include_patterns)
        if effective_token:
            kwargs["token"] = effective_token

        try:
            summary, tree, raw_content = await ingest_async(repo_url, **kwargs)
        except Exception as exc:
            raise RepoIngestError(
                _format_ingest_error(exc, effective_token)
            ) from exc

        content = _parse_gitingest_content(raw_content)
        if not content:
            raise RepoIngestError(
                "repository ingest returned no file content (check include/exclude patterns)"
            )

        total_size = sum(
            len(v.encode("utf-8", errors="ignore")) for v in content.values()
        )
        if total_size > self._max_bytes:
            raise RepoIngestError(
                f"repository content exceeds max size ({self._max_bytes} bytes)"
            )

        return RepoDigest(
            summary=summary or "",
            tree=tree or "",
            content=content,
            source_uri=repo_url,
        )
