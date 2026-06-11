"""GitingestAdapter 单元测试。"""

from __future__ import annotations

import pytest

from mo_api.adapters.repo_ingest import GitingestAdapter, RepoIngestError
from mo_api.models.repo import RepoDigest


@pytest.mark.asyncio
async def test_ingest_maps_to_repo_digest(monkeypatch) -> None:
    async def fake_ingest_async(repo_url: str, **kwargs):
        assert kwargs.get("exclude_patterns")
        return ("summary text", "tree text", {"README.md": "hello"})

    monkeypatch.setitem(
        __import__("sys").modules,
        "gitingest",
        type("M", (), {"ingest_async": staticmethod(fake_ingest_async)})(),
    )

    adapter = GitingestAdapter()
    digest = await adapter.ingest("https://github.com/o/r")

    assert isinstance(digest, RepoDigest)
    assert digest.summary == "summary text"
    assert digest.content["README.md"] == "hello"
    assert digest.source_uri == "https://github.com/o/r"


@pytest.mark.asyncio
async def test_ingest_rejects_oversized_content(monkeypatch) -> None:
    async def fake_ingest_async(repo_url: str, **kwargs):
        return ("s", "t", {"big.txt": "x" * 100})

    monkeypatch.setitem(
        __import__("sys").modules,
        "gitingest",
        type("M", (), {"ingest_async": staticmethod(fake_ingest_async)})(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.get_settings",
        lambda: type(
            "S",
            (),
            {
                "repo_ingest_max_bytes": 10,
                "repo_ingest_exclude_patterns": ".git",
            },
        )(),
    )

    adapter = GitingestAdapter()
    with pytest.raises(RepoIngestError, match="max size"):
        await adapter.ingest("https://github.com/o/r")


@pytest.mark.asyncio
async def test_import_error_raises_repo_ingest_error(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "gitingest":
            raise ImportError("no gitingest")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    adapter = GitingestAdapter()
    with pytest.raises(RepoIngestError, match="not installed"):
        await adapter.ingest("https://github.com/o/r")
