"""ModelGateway 单元与路由测试（PRD F-012）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mo_api.adapters.model_gateway.gateway import ModelCallError, ModelGateway
from mo_api.adapters.model_gateway.profiles import (
    ModelConfigError,
    ProfileStore,
    load_profiles,
    reset_profiles_cache,
)
from mo_api.adapters.model_gateway.gateway import reset_model_gateway_cache
from mo_api.config import get_settings


@pytest.fixture
def profiles_file(tmp_path: Path) -> Path:
    config = {
        "default_routes": {
            "reasoning": "deepseek-reasoning",
            "vision": "kimi-vision",
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
            },
            {
                "id": "deepseek-flash",
                "provider": "deepseek",
                "model_name": "deepseek-v4-flash",
                "api_key_env": "DEEPSEEK_API_KEY",
                "capabilities": {"text": True, "json_mode": True},
                "default_temperature": 0.1,
            },
            {
                "id": "kimi-vision",
                "provider": "moonshot",
                "model_name": "kimi-k2.6",
                "api_key_env": "KIMI_API_KEY",
                "capabilities": {"text": True, "vision": True},
            },
        ],
    }
    path = tmp_path / "model_profiles.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def no_vision_profiles_file(tmp_path: Path) -> Path:
    config = {
        "default_routes": {"reasoning": "deepseek-reasoning"},
        "profiles": [
            {
                "id": "deepseek-reasoning",
                "provider": "deepseek",
                "model_name": "deepseek-v4-pro",
                "api_key_env": "DEEPSEEK_API_KEY",
                "capabilities": {"text": True, "reasoning": True},
            }
        ],
    }
    path = tmp_path / "no_vision.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def store(profiles_file: Path) -> ProfileStore:
    return ProfileStore(load_profiles(profiles_file))


@pytest.fixture
def gateway(store: ProfileStore) -> ModelGateway:
    return ModelGateway(store)


def test_load_profiles_parses_json(profiles_file: Path) -> None:
    config = load_profiles(profiles_file)
    assert len(config.profiles) == 3
    assert config.default_routes["vision"] == "kimi-vision"


def test_select_reasoning_uses_default_route(gateway: ModelGateway) -> None:
    profile = gateway.select(need_reasoning=True)
    assert profile.id == "deepseek-reasoning"


def test_select_vision_uses_kimi(gateway: ModelGateway) -> None:
    profile = gateway.select(need_vision=True)
    assert profile.id == "kimi-vision"


def test_select_vision_without_profile_raises(
    no_vision_profiles_file: Path,
) -> None:
    store = ProfileStore(load_profiles(no_vision_profiles_file))
    gw = ModelGateway(store)
    with pytest.raises(ModelConfigError, match="no model profile satisfies"):
        gw.select(need_vision=True)


def test_has_api_key_false_when_env_missing(store: ProfileStore, monkeypatch) -> None:
    profile = store.by_id("deepseek-reasoning")
    assert profile is not None
    # load_dotenv() 可能会从 .env 注入真实 Key；测试时显式清除
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert store.has_api_key(profile) is False


def test_has_api_key_true_when_env_set(store: ProfileStore, monkeypatch) -> None:
    profile = store.by_id("deepseek-reasoning")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    assert store.has_api_key(profile) is True


@pytest.mark.asyncio
async def test_complete_uses_api_key_env(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-key-value")

    class _Choice:
        message = type("M", (), {"content": "hello"})()

    class _Response:
        choices = [_Choice()]

    def fake_completion(*_args, **kwargs):
        assert kwargs["api_key"] == "secret-key-value"
        return _Response()

    from mo_api.adapters.model_gateway.gateway import ModelGateway as GW

    monkeypatch.setattr(
        GW,
        "_import_litellm",
        staticmethod(
            lambda: type("L", (), {"completion": fake_completion})(),
        ),
    )

    result = await gateway.complete(profile, [{"role": "user", "content": "hi"}])
    assert result == "hello"


@pytest.mark.asyncio
async def test_complete_missing_key_raises_config_error(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    from mo_api.adapters.model_gateway.gateway import ModelGateway as GW

    monkeypatch.setattr(GW, "_import_litellm", staticmethod(lambda: object()))

    with pytest.raises(ModelConfigError, match="DEEPSEEK_API_KEY"):
        await gateway.complete(profile, [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_complete_wraps_call_errors(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-key-value")

    def boom(*_args, **_kwargs):
        raise RuntimeError("provider exploded with sk-secret")

    from mo_api.adapters.model_gateway.gateway import ModelGateway as GW

    monkeypatch.setattr(
        GW,
        "_import_litellm",
        staticmethod(lambda: type("L", (), {"completion": boom})()),
    )
    gw = ModelGateway(store)
    gw.max_retries = 0

    with pytest.raises(ModelCallError) as exc:
        await gw.complete(profile, [{"role": "user", "content": "hi"}])
    assert "sk-secret" not in str(exc.value)


# ── select() explicit profile_id ──


def test_select_explicit_profile_id(gateway: ModelGateway) -> None:
    """通过 profile_id 显式选择应直接返回该 profile。"""
    profile = gateway.select(profile_id="deepseek-flash")
    assert profile.id == "deepseek-flash"


def test_select_explicit_profile_id_insufficient_capabilities(
    gateway: ModelGateway,
) -> None:
    """显式指定 profile_id 但能力不满足需求时抛 ModelConfigError。"""
    with pytest.raises(ModelConfigError, match="does not satisfy"):
        gateway.select(profile_id="deepseek-flash", need_reasoning=True)


def test_select_unknown_profile_id(gateway: ModelGateway) -> None:
    """未知 profile_id 抛 ModelConfigError。"""
    with pytest.raises(ModelConfigError, match="unknown model profile"):
        gateway.select(profile_id="nonexistent")


def test_select_combined_capabilities(gateway: ModelGateway) -> None:
    """同时需要 reasoning + json 时应优先匹配同时满足两者的 profile。"""
    profile = gateway.select(need_reasoning=True, need_json=True)
    assert profile.id == "deepseek-reasoning"


def test_default_routes_order_respected(gateway: ModelGateway, store: ProfileStore) -> None:
    """不需要特定能力时，以 default_routes 中首次出现的 profile 为准。"""
    profile = gateway.select()
    # deepseek-reasoning 在 default_routes 中出现最早
    assert profile.id == "deepseek-reasoning"


# ── gateway.test_profile ──


@pytest.mark.asyncio
async def test_test_profile_success(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    """test_profile 在 complete 成功时返回 ok=True 及响应预览和延迟。"""
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    async def fake_complete(self, profile, messages, **kwargs):
        return "pong"

    monkeypatch.setattr(ModelGateway, "complete", fake_complete)
    ok, message, latency = await gateway.test_profile(profile)
    assert ok is True
    assert "pong" in message
    assert latency >= 0


@pytest.mark.asyncio
async def test_test_profile_failure(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    """test_profile 在 complete 抛 ModelCallError 时返回 ok=False。"""
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    async def fake_complete(self, profile, messages, **kwargs):
        raise ModelCallError("provider error")

    monkeypatch.setattr(ModelGateway, "complete", fake_complete)
    ok, message, latency = await gateway.test_profile(profile)
    assert ok is False
    assert "provider error" in message
    assert latency >= 0


# ── complete() with base_url / retry ──


@pytest.mark.asyncio
async def test_complete_with_base_url(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    """complete() 应把 env DEEPSEEK_BASE_URL 作为 api_base 传入 litellm。"""
    profile = store.by_id("deepseek-reasoning")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://custom.deepseek.com/v1")

    class _Choice:
        message = type("M", (), {"content": "hello"})()

    class _Response:
        choices = [_Choice()]

    captured: dict = {}

    def fake_completion(*args, **kwargs):
        captured.update(kwargs)
        return _Response()

    monkeypatch.setattr(
        ModelGateway,
        "_import_litellm",
        staticmethod(lambda: type("L", (), {"completion": fake_completion})()),
    )

    result = await gateway.complete(profile, [{"role": "user", "content": "hi"}])
    assert result == "hello"
    assert captured.get("api_base") == "https://custom.deepseek.com/v1"


@pytest.mark.asyncio
async def test_complete_retry_transient_succeeds(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    """瞬时错误重试后最终成功。"""
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    class _Choice:
        message = type("M", (), {"content": "ok"})

    class _Response:
        choices = [_Choice()]

    call_count = 0

    def fake_completion(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient failure")
        return _Response()

    monkeypatch.setattr(
        ModelGateway,
        "_import_litellm",
        staticmethod(lambda: type("L", (), {"completion": fake_completion})()),
    )

    gw = ModelGateway(store)
    gw.max_retries = 2
    result = await gw.complete(profile, [{"role": "user", "content": "hi"}])
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_complete_no_retry_on_auth_error(
    gateway: ModelGateway, store: ProfileStore, monkeypatch
) -> None:
    """认证错误 (AuthenticationError) 不应重试，直接抛 ModelCallError。"""
    profile = store.by_id("deepseek-flash")
    assert profile is not None
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    call_count = 0

    from litellm import exceptions as litellm_exc

    def fake_completion(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise litellm_exc.AuthenticationError(
            message="bad key",
            llm_provider="deepseek",
            model="deepseek-v4-flash",
        )

    _fake_litellm = type("L", (), {"completion": staticmethod(fake_completion)})()

    monkeypatch.setattr(
        ModelGateway, "_import_litellm", staticmethod(lambda: _fake_litellm)
    )

    gw = ModelGateway(store)
    gw.max_retries = 2
    with pytest.raises(ModelCallError):
        await gw.complete(profile, [{"role": "user", "content": "hi"}])
    assert call_count == 1  # 仅一次，无重试


@pytest.fixture
def patched_profiles(monkeypatch, profiles_file: Path):
    monkeypatch.setenv("MODEL_PROFILES_PATH", str(profiles_file))
    get_settings.cache_clear()
    reset_profiles_cache()
    reset_model_gateway_cache()
    yield
    get_settings.cache_clear()
    reset_profiles_cache()
    reset_model_gateway_cache()


@pytest.mark.asyncio
async def test_capabilities_endpoint(client, patched_profiles) -> None:
    resp = await client.get("/api/models/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["profiles"]) == 3
    assert "default_routes" in body
    for profile in body["profiles"]:
        assert "api_key" not in profile
        assert "api_key_env" not in profile
        assert "has_api_key" in profile


@pytest.mark.asyncio
async def test_test_endpoint_missing_key_returns_409(
    client, patched_profiles, monkeypatch
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    resp = await client.post(
        "/api/models/test",
        json={"profile_id": "deepseek-reasoning"},
    )
    assert resp.status_code == 409
    assert "DEEPSEEK_API_KEY" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_test_endpoint_success_mocked(
    client, patched_profiles, monkeypatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    async def fake_test(self, profile):
        return True, "ok: pong", 12

    monkeypatch.setattr(
        "mo_api.adapters.model_gateway.gateway.ModelGateway.test_profile",
        fake_test,
    )

    resp = await client.post(
        "/api/models/test",
        json={"profile_id": "deepseek-flash"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["profile_id"] == "deepseek-flash"
    assert body["latency_ms"] == 12

