"""真实 paper-qa 集成验证测试（PRD F-006, MO_Backend §7.3）。

本测试验证：
- paper-qa 库可真实导入，API 签名与适配器期望一致
- ModelGateway → _llm_model_string() 产出 paper-qa 接受的 provider/model 格式
- 适配器与真实 paper-qa Settings / Docs 对象正确交互
- 错误路径（空文档、文件不存在）优雅降级

注意：本测试不会发起真实 LLM 调用（遵守 R-004），仅验证集成契约。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mo_api.adapters.model_gateway.gateway import (
    ModelGateway,
    reset_model_gateway_cache,
)
from mo_api.adapters.model_gateway.profiles import (
    ProfileStore,
    reset_profiles_cache,
)
from mo_api.models.model import ModelProfilesConfig


# ──▸ model_profiles.json 测试 fixture ◂──────────────────────────────
@pytest.fixture
def model_profiles_path(tmp_path: Path) -> str:
    """创建最小 model_profiles.json，匹配 .env 中的 DEEPSEEK_API_KEY。"""
    config = {
        "default_routes": {
            "reasoning": "deepseek-reasoning",
            "summarize": "deepseek-flash",
        },
        "profiles": [
            {
                "id": "deepseek-reasoning",
                "provider": "deepseek",
                "model_name": "deepseek-v4-pro",
                "api_key_env": "DEEPSEEK_API_KEY",
                "base_url_env": "DEEPSEEK_BASE_URL",
                "capabilities": {
                    "text": True,
                    "reasoning": True,
                    "json_mode": True,
                    "long_context": True,
                },
                "default_temperature": 0.3,
                "reasoning_effort": "medium",
            },
            {
                "id": "deepseek-flash",
                "provider": "deepseek",
                "model_name": "deepseek-v4-flash",
                "api_key_env": "DEEPSEEK_API_KEY",
                "base_url_env": "DEEPSEEK_BASE_URL",
                "capabilities": {"text": True, "json_mode": True},
                "default_temperature": 0.1,
            },
        ],
    }
    path = tmp_path / "model_profiles.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


@pytest.fixture
def gateway_with_profiles(model_profiles_path: str, monkeypatch):
    """注入临时 model_profiles.json + 重置缓存，构建真实 ModelGateway。"""
    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.profiles.get_settings",
        lambda: type(
            "S",
            (),
            {"model_profiles_path": model_profiles_path},
        )(),
    )
    monkeypatch.setattr(
        "mo_api.adapters.paper_research.paperqa_adapter.get_model_gateway",
        lambda: ModelGateway(
            ProfileStore(ModelProfilesConfig.model_validate(json.loads(
                Path(model_profiles_path).read_text(encoding="utf-8")
            )))
        ),
    )
    reset_profiles_cache()
    reset_model_gateway_cache()
    yield
    reset_profiles_cache()
    reset_model_gateway_cache()


# ──▸ 1. 真实导入 + API 签名验证 ◂──────────────────────────────────
def test_paperqa_library_importable():
    """验证 paper-qa 库可导入且 API 表面与适配器期望一致。（F-006）"""
    from paperqa import Docs, Settings

    # 构造函数签名检查
    settings = Settings(llm="openai/gpt-4o", summary_llm="openai/gpt-4o-mini")
    assert settings.llm == "openai/gpt-4o"
    assert settings.summary_llm == "openai/gpt-4o-mini"

    # embedding 参数存在（paper-qa >= 5.x 支持）
    assert hasattr(settings, "embedding"), "Settings 缺少 embedding 字段"

    docs = Docs()
    assert hasattr(docs, "aadd"), "Docs 缺少 aadd 方法"
    assert hasattr(docs, "aquery"), "Docs 缺少 aquery 方法"
    assert callable(docs.aadd)
    assert callable(docs.aquery)


def test_paperqa_version():
    """验证 paper-qa 版本号可读。"""
    import paperqa

    version = getattr(paperqa, "__version__", None)
    assert version is not None, "paper-qa 缺少 __version__"
    # 版本字符串应包含年份（paper-qa 使用 calver）
    assert "2026" in version or "2025" in version, f"unexpected version: {version}"


# ──▸ 2. ModelGateway → paper-qa LLM 字符串格式验证 ◂───────────────
def test_llm_model_string_format(gateway_with_profiles):
    """验证 _llm_model_string() 产出的 provider/model 格式被 paper-qa Settings 接受。（F-012 + F-006）"""
    from mo_api.adapters.paper_research import PaperQAAdapter

    adapter = PaperQAAdapter()
    llm_str = adapter._llm_model_string()

    assert llm_str, "LLM model string 不应为空"
    assert "/" in llm_str, f"LLM model string 缺少 provider/model 分隔符: {llm_str!r}"
    assert "deepseek" in llm_str.lower(), f"期望 deepseek 模型，得到: {llm_str!r}"

    # 验证该字符串能被 paper-qa Settings 接受
    from paperqa import Settings

    s = Settings(llm=llm_str, summary_llm=llm_str, embedding=llm_str)
    assert s.llm == llm_str


def test_llm_model_string_consistent(gateway_with_profiles):
    """验证每次调用 _llm_model_string() 返回一致结果。"""
    from mo_api.adapters.paper_research import PaperQAAdapter

    adapter = PaperQAAdapter()
    a = adapter._llm_model_string()
    b = adapter._llm_model_string()
    assert a == b, "多次调用 _llm_model_string() 应返回一致结果"


# ──▸ 3. 适配器与真实 paper-qa 对象交互 ◂───────────────────────────
def test_paperqa_settings_creation_with_model_string(gateway_with_profiles):
    """验证使用我们的 LLM 字符串可正常创建 paper-qa Settings 对象。"""
    from paperqa import Settings

    from mo_api.adapters.paper_research import PaperQAAdapter

    adapter = PaperQAAdapter()
    llm_str = adapter._llm_model_string()

    # 创建 Settings（不发起任何网络调用）
    settings = Settings(
        llm=llm_str,
        summary_llm=llm_str,
        embedding=llm_str,
    )

    assert settings.llm == llm_str
    assert settings.summary_llm == llm_str
    assert settings.embedding == llm_str


def test_paperqa_docs_construction():
    """验证 paper-qa Docs 对象可正常构造。"""
    from paperqa import Docs

    docs = Docs()
    assert docs is not None
    # Docs 对象在未添加文档前不应有内容
    assert hasattr(docs, "docs"), "Docs 缺少 docs 属性"


# ──▸ 4. 错误路径验证 ◂─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_doc_paths_returns_empty():
    """验证空文档列表直接返回空结果，不走 paper-qa 调用。"""
    from mo_api.adapters.paper_research import PaperQAAdapter

    adapter = PaperQAAdapter()
    result = await adapter.query_papers([], question="test", task_id="t-empty")
    assert result.answer == ""
    assert result.contexts == []


@pytest.mark.asyncio
async def test_nonexistent_file_graceful_degradation(monkeypatch, tmp_path):
    """验证文件不存在时适配器优雅降级（不崩溃，continue 处理）。"""
    from mo_api.adapters.paper_research import PaperQAAdapter

    # 构造一个假 gateway 返回合理 profile
    class _FakeProfile:
        id = "fake"
        provider = "openai"
        model_name = "gpt-test"
        api_key_env = "OPENAI_API_KEY"

    class _FakeGateway:
        def select(self, **kwargs):
            return _FakeProfile()

    # 设置环境变量避免 ModelConfigError
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-dummy")

    adapter = PaperQAAdapter(model_gateway=_FakeGateway())

    # 给一个不存在的文件路径 — paper-qa aadd 会在内部抛异常
    # 适配器应 catch 并标记 failed，最终返回空结果
    nonexistent = str(tmp_path / "nonexistent.pdf")
    result = await adapter.query_papers(
        [nonexistent], question="test", task_id="t-missing"
    )

    # 所有文件都失败了 → 应返回空答案
    assert result.answer == ""
    assert result.contexts == []


@pytest.mark.asyncio
async def test_paperqa_not_installed_fallback(monkeypatch):
    """验证 paper-qa 未安装时抛出 PaperResearchError。（回归 F-006）"""
    import builtins

    from mo_api.adapters.paper_research import PaperQAAdapter, PaperResearchError

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "paperqa":
            raise ImportError("no paperqa")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    class _FakeGateway:
        def select(self, **kwargs):
            return type("P", (), {"provider": "x", "model_name": "y"})()

    adapter = PaperQAAdapter(model_gateway=_FakeGateway())

    with pytest.raises(PaperResearchError, match="not installed"):
        await adapter.query_papers(["/tmp/x.pdf"], question="q", task_id="t1")


# ──▸ 5. 错误消息脱敏验证 ◂─────────────────────────────────────────
@pytest.mark.asyncio
async def test_sanitize_error_messages(monkeypatch, tmp_path):
    """验证 paper-qa 异常中的敏感信息被脱敏。（F-006）"""
    from mo_api.adapters.paper_research import PaperQAAdapter, PaperResearchError

    class _FakeGateway:
        def select(self, **kwargs):
            return type("P", (), {"provider": "x", "model_name": "y"})()

    # Mock paperqa 模块使其 aquery 抛出带敏感信息的异常
    import sys

    class _BoomDocs:
        async def aadd(self, path, settings=None, *, embedding_model=None):
            return None

        async def aquery(self, question, settings=None, *, embedding_model=None):
            raise RuntimeError("api_key=secret123 token=ghp_ABCDEFGH")

    fake_paperqa = type("paperqa", (), {
        "Docs": _BoomDocs,
        "Settings": lambda **kw: object(),
    })
    monkeypatch.setitem(sys.modules, "paperqa", fake_paperqa)

    adapter = PaperQAAdapter(model_gateway=_FakeGateway())

    # 创建一个真实文件让 aadd 成功，然后 aquery 会抛出异常
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content", encoding="utf-8")

    with pytest.raises(PaperResearchError) as exc:
        await adapter.query_papers([str(test_file)], question="q", task_id="t-sanitize")

    msg = str(exc.value)
    assert "secret123" not in msg
    assert "ghp_" not in msg
    assert "[REDACTED]" in msg
