"""repo URL 校验单测（PRD F-001）。

合法 GitHub URL 通过；本地/内网/非 github 被拒；数量越界被拒。
"""

from __future__ import annotations

import pytest

from mo_api.models.validators import (
    RepoUrlError,
    is_valid_github_repo_url,
    validate_repo_urls,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo",
        "https://github.com/owner/repo.git",
        "https://github.com/owner/repo/",
        "https://github.com/Owner-1/repo_name",
        "https://github.com/owner/repo/tree/main/src",
        "https://github.com/owner/repo/blob/main/README.md",
    ],
)
def test_valid_github_urls(url: str) -> None:
    assert is_valid_github_repo_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",          # 非 https
        "https://gitlab.com/owner/repo",          # 非 github
        "https://github.com/owner",               # 缺 repo
        "git@github.com:owner/repo.git",          # ssh 形式
        "file:///etc/passwd",                     # 本地路径
        "https://127.0.0.1/owner/repo",           # 内网
        "https://192.168.0.1/owner/repo",         # 内网
        "/local/path/repo",                       # 本地路径
        "ftp://github.com/owner/repo",            # 非 http
        "",                                        # 空
    ],
)
def test_invalid_github_urls(url: str) -> None:
    assert is_valid_github_repo_url(url) is False


def test_validate_repo_urls_ok() -> None:
    urls = ["https://github.com/a/b", "https://github.com/c/d"]
    assert validate_repo_urls(urls) == urls


def test_validate_repo_urls_strips_whitespace() -> None:
    assert validate_repo_urls(["  https://github.com/a/b  "]) == [
        "https://github.com/a/b"
    ]


def test_validate_repo_urls_empty_rejected() -> None:
    with pytest.raises(RepoUrlError):
        validate_repo_urls([])


def test_validate_repo_urls_too_many_rejected() -> None:
    urls = [f"https://github.com/o/r{i}" for i in range(6)]
    with pytest.raises(RepoUrlError):
        validate_repo_urls(urls)


def test_validate_repo_urls_invalid_member_rejected() -> None:
    with pytest.raises(RepoUrlError):
        validate_repo_urls(["https://github.com/a/b", "not-a-url"])
