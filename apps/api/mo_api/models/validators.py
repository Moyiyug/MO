"""共享校验逻辑。

repo URL 校验：仅允许公开 GitHub 仓库 URL（可含 /tree/... 子路径），
拒绝本地路径、内网地址、非 github 主机。参见 PRD F-001、MO_Backend.md §5。
"""

from __future__ import annotations

import re

# repo_urls 改为可选（F-015）：创建任务时可留空，由 RepoDiscovery 自动发现。
# 仍校验上限与单条 URL 合法性。
MIN_REPO_COUNT = 0
MAX_REPO_COUNT = 5

# https://github.com/<owner>/<repo>  其中 owner/repo 允许字母数字、._-
# 允许可选的 .git 后缀与 /tree/<...>、/blob/<...> 等子路径
_GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9._-]*)/"
    r"(?P<repo>[A-Za-z0-9][A-Za-z0-9._-]*?)(?:\.git)?"
    r"(?:/(?:tree|blob)/[^\s]+)?/?$"
)


class RepoUrlError(ValueError):
    """repo URL 不合法时抛出。"""


def is_valid_github_repo_url(url: str) -> bool:
    """判断单个 URL 是否是合法的公开 GitHub 仓库 URL。"""
    if not isinstance(url, str):
        return False
    return bool(_GITHUB_REPO_RE.match(url.strip()))


def validate_repo_urls(urls: list[str]) -> list[str]:
    """校验 repo URL 列表：数量 1-5，且每个都是合法 GitHub URL。

    返回去除首尾空白后的 URL 列表；任何不合法都会抛 RepoUrlError。
    """
    if not isinstance(urls, list):
        raise RepoUrlError("repo_urls must be a list")

    cleaned = [u.strip() for u in urls]

    if len(cleaned) < MIN_REPO_COUNT or len(cleaned) > MAX_REPO_COUNT:
        raise RepoUrlError(
            f"repo_urls count must be between {MIN_REPO_COUNT} and {MAX_REPO_COUNT}, "
            f"got {len(cleaned)}"
        )

    for url in cleaned:
        if not is_valid_github_repo_url(url):
            raise RepoUrlError(f"invalid GitHub repo URL: {url!r}")

    return cleaned
