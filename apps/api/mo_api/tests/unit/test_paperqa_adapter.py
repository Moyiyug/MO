"""PaperQA 适配器单元测试（PRD F-006）。"""

from __future__ import annotations

import pytest

from mo_api.adapters.paper_research import PaperQAAdapter, PaperResearchError


class _FakeProfile:
    id = "fake"
    provider = "openai"
    model_name = "gpt-test"
    api_key_env = "OPENAI_API_KEY"
    base_url_env = None


class _FakeStore:
    def resolve_api_key(self, profile):
        return "test-key"

    def resolve_base_url(self, profile):
        return None


class _FakeGateway:
    store = _FakeStore()

    def select(self, **kwargs):
        return _FakeProfile()


class _FakeContext:
    text = "paper excerpt about RAG"
    name = "demo.pdf"


class _FakeSession:
    answer = "RAG summary"
    contexts = [_FakeContext()]


class _FakeDocs:
    async def aadd(self, path, settings=None):
        return None

    async def aquery(self, question, settings=None):
        return _FakeSession()


@pytest.mark.asyncio
async def test_paperqa_adapter_maps_contexts(monkeypatch, tmp_path) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_text("demo", encoding="utf-8")

    fake_paperqa = type(
        "paperqa",
        (),
        {
            "Docs": _FakeDocs,
            "Settings": lambda **kwargs: object(),
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "paperqa", fake_paperqa)
    monkeypatch.setattr(
        "mo_api.adapters.paper_research.paperqa_adapter.get_settings",
        lambda: type("S", (), {"paper_index_dir": str(tmp_path / "idx")})(),
    )

    adapter = PaperQAAdapter(model_gateway=_FakeGateway())
    result = await adapter.query_papers(
        [str(pdf)], question="summarize", task_id="t1"
    )

    assert result.answer == "RAG summary"
    assert len(result.contexts) == 1
    assert "RAG" in result.contexts[0].text


@pytest.mark.asyncio
async def test_paperqa_adapter_not_installed(monkeypatch) -> None:
    monkeypatch.delitem(__import__("sys").modules, "paperqa", raising=False)

    def _raise_import(*args, **kwargs):
        raise ImportError("no paperqa")

    monkeypatch.setitem(
        __import__("sys").modules,
        "paperqa",
        type("paperqa", (), {"Docs": _raise_import, "Settings": _raise_import})(),
    )
    # Force re-import path by deleting cached module references - adapter imports inside method
    adapter = PaperQAAdapter(model_gateway=_FakeGateway())

    # Patch import inside method
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "paperqa":
            raise ImportError("no paperqa")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(PaperResearchError, match="not installed"):
        await adapter.query_papers(["/tmp/x.pdf"], question="q", task_id="t1")


@pytest.mark.asyncio
async def test_paperqa_adapter_sanitizes_errors(monkeypatch, tmp_path) -> None:
    pdf = tmp_path / "demo.pdf"
    pdf.write_text("demo", encoding="utf-8")

    class _BoomDocs:
        async def aadd(self, path, settings=None):
            return None

        async def aquery(self, question, settings=None):
            raise RuntimeError("api_key=secret123 token=ghp_abc")

    fake_paperqa = type(
        "paperqa",
        (),
        {
            "Docs": _BoomDocs,
            "Settings": lambda **kwargs: object(),
        },
    )
    monkeypatch.setitem(__import__("sys").modules, "paperqa", fake_paperqa)
    monkeypatch.setattr(
        "mo_api.adapters.paper_research.paperqa_adapter.get_settings",
        lambda: type("S", (), {"paper_index_dir": str(tmp_path / "idx")})(),
    )

    adapter = PaperQAAdapter(model_gateway=_FakeGateway())
    with pytest.raises(PaperResearchError) as exc:
        await adapter.query_papers([str(pdf)], question="q", task_id="t1")
    assert "secret123" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)
