"""GitingestAdapter 单元测试。"""

from __future__ import annotations

import pytest

from mo_api.adapters.repo_ingest import GitingestAdapter, RepoIngestError
from mo_api.adapters.repo_ingest.gitingest_adapter import _sanitize_error
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
async def test_ingest_parses_string_content_blob(monkeypatch) -> None:
    blob = (
        "================================================\n"
        "FILE: README.md\n"
        "================================================\n"
        "hello world\n\n"
        "================================================\n"
        "FILE: src/main.py\n"
        "================================================\n"
        "print('ok')\n"
    )

    async def fake_ingest_async(repo_url: str, **kwargs):
        return ("summary text", "tree text", blob)

    monkeypatch.setitem(
        __import__("sys").modules,
        "gitingest",
        type("M", (), {"ingest_async": staticmethod(fake_ingest_async)})(),
    )

    adapter = GitingestAdapter()
    digest = await adapter.ingest("https://github.com/o/r")

    assert digest.content["README.md"] == "hello world"
    assert "print('ok')" in digest.content["src/main.py"]


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
async def test_ingest_retries_lightweight_on_timeout(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_ingest_async(repo_url: str, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise TimeoutError("Operation timed out after 60 seconds")
        return ("summary text", "tree text", {"README.md": "hello"})

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
                "repo_ingest_max_bytes": 50_000_000,
                "repo_ingest_exclude_patterns": ".git",
                "repo_ingest_include_patterns": "*.md,*.py,*.json",
            },
        )(),
    )

    adapter = GitingestAdapter()
    digest = await adapter.ingest("https://github.com/o/r")

    assert digest.content["README.md"] == "hello"
    assert len(calls) == 2
    assert "include_patterns" in calls[1]
    assert "*.md" in calls[1]["include_patterns"]
    assert "pyproject.toml" in calls[1]["include_patterns"]


def test_include_patterns_normalize_dot_extensions(monkeypatch) -> None:
    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.get_settings",
        lambda: type(
            "S",
            (),
            {
                "repo_ingest_max_bytes": 50_000_000,
                "repo_ingest_exclude_patterns": ".git",
                "repo_ingest_include_patterns": ".md,.py,*.json",
            },
        )(),
    )
    adapter = GitingestAdapter()
    assert adapter._include_patterns == ["*.md", "*.py", "*.json"]


def test_sanitize_error_redacts_basic_auth_header() -> None:
    message = (
        "git -c http.https://github.com/.extraheader=Authorization: Basic "
        "YWJjMTIz checkout failed"
    )
    sanitized = _sanitize_error(message)
    assert "YWJjMTIz" not in sanitized
    assert "Authorization: Basic [REDACTED]" in sanitized


@pytest.mark.asyncio
async def test_ingest_prefers_raw_fallback_for_known_long_path_repo(
    monkeypatch,
) -> None:
    calls = {"gitingest": 0}

    async def fake_ingest_async(repo_url: str, **kwargs):
        calls["gitingest"] += 1
        return ("summary text", "tree text", {"README.md": "from gitingest"})

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            return b"# LlamaIndex\nRaw fallback content."

    def fake_urlopen(request, timeout: int = 20):
        if request.full_url.endswith("/README.md"):
            return FakeResponse()
        raise RuntimeError("404")

    monkeypatch.setitem(
        __import__("sys").modules,
        "gitingest",
        type("M", (), {"ingest_async": staticmethod(fake_ingest_async)})(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.urlopen",
        fake_urlopen,
    )

    adapter = GitingestAdapter()
    digest = await adapter.ingest("https://github.com/run-llama/llama_index")

    assert digest.content["README.md"].startswith("# LlamaIndex")
    assert calls["gitingest"] == 0


@pytest.mark.asyncio
async def test_ingest_uses_raw_fallback_on_checkout_path_error(monkeypatch) -> None:
    async def fake_ingest_async(repo_url: str, **kwargs):
        raise RuntimeError(
            "fatal: cannot create directory at "
            "'llama-index-integrations/postprocessor/very-long-path'"
        )

    class FakeResponse:
        status = 200

        def __init__(self, text: str) -> None:
            self._text = text

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            return self._text.encode("utf-8")

    def fake_urlopen(request, timeout: int = 20):
        url = request.full_url
        if url.endswith("/README.md"):
            return FakeResponse("# LlamaIndex\nA framework for RAG applications.")
        if url.endswith("/pyproject.toml"):
            return FakeResponse("[project]\nname = 'llama-index'\n")
        raise RuntimeError("404")

    monkeypatch.setitem(
        __import__("sys").modules,
        "gitingest",
        type("M", (), {"ingest_async": staticmethod(fake_ingest_async)})(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "mo_api.adapters.repo_ingest.gitingest_adapter.get_settings",
        lambda: type(
            "S",
            (),
            {
                "repo_ingest_max_bytes": 50_000_000,
                "repo_ingest_exclude_patterns": ".git",
                "repo_ingest_include_patterns": "*.md,*.py,*.json",
            },
        )(),
    )

    adapter = GitingestAdapter()
    digest = await adapter.ingest("https://github.com/run-llama/llama_index")

    assert digest.content["README.md"].startswith("# LlamaIndex")
    assert "pyproject.toml" in digest.content
    assert "Raw GitHub fallback ingest" in digest.summary


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
