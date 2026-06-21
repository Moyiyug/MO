"""gitingest 仓库摄取适配器（MO_Backend §7.2）。"""

from __future__ import annotations

import asyncio
import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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

_LIGHTWEIGHT_INCLUDE_PATTERNS: tuple[str, ...] = (
    "*.md",
    "*.rst",
    "README",
    "README.*",
    "LICENSE",
    "LICENSE.*",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements*.txt",
    "package.json",
    "Dockerfile",
    "Makefile",
    "*.yaml",
    "*.yml",
    "docs/**/*.md",
    "examples/**/*.py",
    "tests/**/*.py",
)

_RAW_FALLBACK_FILES: tuple[str, ...] = (
    "README.md",
    "README.rst",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "package.json",
    "LICENSE",
    "LICENSE.md",
    "docs/index.md",
    "docs/docs/index.md",
)

_RAW_FALLBACK_BRANCHES: tuple[str, ...] = ("main", "master")
_RAW_FALLBACK_FILE_BYTES = 250_000
_RAW_FIRST_REPOS: set[tuple[str, str]] = {
    ("run-llama", "llama_index"),
}


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
    text = re.sub(
        r"(?i)Authorization:\s*Basic\s+[A-Za-z0-9+/=]+",
        "Authorization: Basic [REDACTED]",
        text,
    )
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


def _should_retry_lightweight(message: str) -> bool:
    lower = (message or "").lower()
    return any(
        marker in lower
        for marker in (
            "timed out",
            "timeout",
            "operation timed out",
            "exceeds max size",
        )
    )


def _is_checkout_path_error(message: str) -> bool:
    lower = (message or "").lower()
    return any(
        marker in lower
        for marker in (
            "cannot create directory",
            "filename too long",
            "path too long",
            "long path",
        )
    )


def _owner_repo(repo_url: str) -> tuple[str, str] | None:
    parsed = urlparse(repo_url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _should_try_raw_first(repo_url: str) -> bool:
    owner_repo = _owner_repo(repo_url)
    if owner_repo is None:
        return False
    owner, repo = owner_repo
    return (owner.lower(), repo.lower()) in _RAW_FIRST_REPOS


def _fetch_raw_file(url: str, token: str | None = None) -> str | None:
    headers = {"User-Agent": "MO-repo-ingest"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        status = getattr(response, "status", 200)
        if status >= 400:
            return None
        data = response.read(_RAW_FALLBACK_FILE_BYTES + 1)
    if not data:
        return None
    return data[:_RAW_FALLBACK_FILE_BYTES].decode("utf-8", errors="replace")


async def _raw_github_fallback_digest(
    repo_url: str,
    *,
    token: str | None = None,
    max_bytes: int,
) -> RepoDigest | None:
    owner_repo = _owner_repo(repo_url)
    if owner_repo is None:
        return None

    owner, repo = owner_repo
    for branch in _RAW_FALLBACK_BRANCHES:
        content: dict[str, str] = {}
        for path in _RAW_FALLBACK_FILES:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            try:
                text = await asyncio.to_thread(_fetch_raw_file, url, token)
            except Exception:
                continue
            if text:
                content[path] = text

            total_size = sum(
                len(value.encode("utf-8", errors="ignore"))
                for value in content.values()
            )
            if total_size >= max_bytes:
                break

        if content:
            tree = "\n".join(sorted(content))
            summary = (
                "Raw GitHub fallback ingest; fetched key public files after "
                "git checkout failed on local filesystem paths. "
                f"Branch: {branch}; files: {', '.join(sorted(content))}."
            )
            return RepoDigest(
                summary=summary,
                tree=tree,
                content=content,
                source_uri=repo_url,
            )

    return None


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
        self._lightweight_include_patterns = [
            _normalize_glob_pattern(p) for p in _LIGHTWEIGHT_INCLUDE_PATTERNS
        ]

    async def ingest(self, repo_url: str, *, token: str | None = None) -> RepoDigest:
        # 读取 GITHUB_TOKEN（参数优先，其次 env）
        effective_token = token
        if effective_token is None:
            effective_token = os.environ.get("GITHUB_TOKEN", "").strip() or None

        if _should_try_raw_first(repo_url):
            fallback = await _raw_github_fallback_digest(
                repo_url,
                token=effective_token,
                max_bytes=self._max_bytes,
            )
            if fallback is not None:
                return fallback

        # BUG-009: Windows schannel 与代理冲突 → 强制 git 用 OpenSSL
        # BUG-011: LFS 仓库 smudge 失败 → 跳过 LFS 文件
        _prev_ssl = os.environ.get("GIT_SSL_BACKEND")
        _prev_lfs = os.environ.get("GIT_LFS_SKIP_SMUDGE")
        _prev_cfg_count = os.environ.get("GIT_CONFIG_COUNT")
        _prev_cfg_key_0 = os.environ.get("GIT_CONFIG_KEY_0")
        _prev_cfg_value_0 = os.environ.get("GIT_CONFIG_VALUE_0")
        os.environ["GIT_SSL_BACKEND"] = "openssl"
        os.environ["GIT_LFS_SKIP_SMUDGE"] = "1"
        os.environ["GIT_CONFIG_COUNT"] = "1"
        os.environ["GIT_CONFIG_KEY_0"] = "core.longpaths"
        os.environ["GIT_CONFIG_VALUE_0"] = "true"

        try:
            from gitingest import ingest_async
        except ImportError as exc:
            raise RepoIngestError(
                "gitingest is not installed; add gitingest to requirements"
            ) from exc

        def _build_kwargs(include_patterns: list[str]) -> dict:
            kwargs: dict = {
                "exclude_patterns": set(self._exclude_patterns),
            }
            if include_patterns:
                kwargs["include_patterns"] = set(include_patterns)
            if effective_token:
                kwargs["token"] = effective_token
            return kwargs

        async def _run_ingest(
            include_patterns: list[str],
        ) -> tuple[str, str, str | dict[str, str]]:
            prev_ssl = os.environ.get("GIT_SSL_BACKEND")
            prev_lfs = os.environ.get("GIT_LFS_SKIP_SMUDGE")
            prev_cfg_count = os.environ.get("GIT_CONFIG_COUNT")
            prev_cfg_key_0 = os.environ.get("GIT_CONFIG_KEY_0")
            prev_cfg_value_0 = os.environ.get("GIT_CONFIG_VALUE_0")
            os.environ["GIT_SSL_BACKEND"] = "openssl"
            os.environ["GIT_LFS_SKIP_SMUDGE"] = "1"
            os.environ["GIT_CONFIG_COUNT"] = "1"
            os.environ["GIT_CONFIG_KEY_0"] = "core.longpaths"
            os.environ["GIT_CONFIG_VALUE_0"] = "true"
            try:
                return await ingest_async(repo_url, **_build_kwargs(include_patterns))
            finally:
                if prev_ssl is None:
                    os.environ.pop("GIT_SSL_BACKEND", None)
                else:
                    os.environ["GIT_SSL_BACKEND"] = prev_ssl
                if prev_lfs is None:
                    os.environ.pop("GIT_LFS_SKIP_SMUDGE", None)
                else:
                    os.environ["GIT_LFS_SKIP_SMUDGE"] = prev_lfs
                if prev_cfg_count is None:
                    os.environ.pop("GIT_CONFIG_COUNT", None)
                else:
                    os.environ["GIT_CONFIG_COUNT"] = prev_cfg_count
                if prev_cfg_key_0 is None:
                    os.environ.pop("GIT_CONFIG_KEY_0", None)
                else:
                    os.environ["GIT_CONFIG_KEY_0"] = prev_cfg_key_0
                if prev_cfg_value_0 is None:
                    os.environ.pop("GIT_CONFIG_VALUE_0", None)
                else:
                    os.environ["GIT_CONFIG_VALUE_0"] = prev_cfg_value_0

        try:
            summary, tree, raw_content = await _run_ingest(self._include_patterns)
        except Exception as exc:
            message = _format_ingest_error(exc, effective_token)
            if _is_checkout_path_error(message):
                fallback = await _raw_github_fallback_digest(
                    repo_url,
                    token=effective_token,
                    max_bytes=self._max_bytes,
                )
                if fallback is not None:
                    return fallback
            if _should_retry_lightweight(message):
                try:
                    summary, tree, raw_content = await _run_ingest(
                        self._lightweight_include_patterns
                    )
                except Exception as retry_exc:
                    retry_message = _format_ingest_error(retry_exc, effective_token)
                    if _is_checkout_path_error(retry_message):
                        fallback = await _raw_github_fallback_digest(
                            repo_url,
                            token=effective_token,
                            max_bytes=self._max_bytes,
                        )
                        if fallback is not None:
                            return fallback
                    raise RepoIngestError(
                        retry_message
                    ) from retry_exc
            else:
                raise RepoIngestError(message) from exc
        finally:
            # 恢复环境变量
            if _prev_ssl is None:
                os.environ.pop("GIT_SSL_BACKEND", None)
            else:
                os.environ["GIT_SSL_BACKEND"] = _prev_ssl
            if _prev_lfs is None:
                os.environ.pop("GIT_LFS_SKIP_SMUDGE", None)
            else:
                os.environ["GIT_LFS_SKIP_SMUDGE"] = _prev_lfs
            if _prev_cfg_count is None:
                os.environ.pop("GIT_CONFIG_COUNT", None)
            else:
                os.environ["GIT_CONFIG_COUNT"] = _prev_cfg_count
            if _prev_cfg_key_0 is None:
                os.environ.pop("GIT_CONFIG_KEY_0", None)
            else:
                os.environ["GIT_CONFIG_KEY_0"] = _prev_cfg_key_0
            if _prev_cfg_value_0 is None:
                os.environ.pop("GIT_CONFIG_VALUE_0", None)
            else:
                os.environ["GIT_CONFIG_VALUE_0"] = _prev_cfg_value_0

        content = _parse_gitingest_content(raw_content)
        if not content:
            raise RepoIngestError(
                "repository ingest returned no file content (check include/exclude patterns)"
            )

        total_size = sum(
            len(v.encode("utf-8", errors="ignore")) for v in content.values()
        )
        if total_size > self._max_bytes:
            if set(self._include_patterns) != set(self._lightweight_include_patterns):
                try:
                    summary, tree, raw_content = await _run_ingest(
                        self._lightweight_include_patterns
                    )
                    content = _parse_gitingest_content(raw_content)
                    if not content:
                        raise RepoIngestError(
                            "repository ingest returned no file content (lightweight retry)"
                        )
                    total_size = sum(
                        len(v.encode("utf-8", errors="ignore"))
                        for v in content.values()
                    )
                except Exception as exc:
                    raise RepoIngestError(
                        _format_ingest_error(exc, effective_token)
                    ) from exc
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
