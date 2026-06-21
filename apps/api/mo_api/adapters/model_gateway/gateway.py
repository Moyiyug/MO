"""ModelGateway：按 capability 路由 + litellm 调用（PRD F-012）。"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import Any

from ...config import get_settings
from ...models.model import ModelProfile
from .profiles import ModelConfigError, ProfileStore, get_profile_store

logger = logging.getLogger("mo_api.model_gateway")


class ModelCallError(Exception):
    """模型调用失败（脱敏，不含 key/堆栈）。"""


_CAPABILITY_CHECKS: list[tuple[str, str]] = [
    ("need_reasoning", "reasoning"),
    ("need_vision", "vision"),
    ("need_json", "json_mode"),
    ("long_context", "long_context"),
]


class ModelGateway:
    def __init__(self, store: ProfileStore) -> None:
        self.store = store
        settings = get_settings()
        self.timeout_seconds = settings.model_call_timeout_seconds
        self.max_retries = settings.model_call_max_retries

    def select(
        self,
        *,
        need_reasoning: bool = False,
        need_vision: bool = False,
        need_json: bool = False,
        long_context: bool = False,
        profile_id: str | None = None,
    ) -> ModelProfile:
        if profile_id:
            profile = self.store.by_id(profile_id)
            if profile is None:
                raise ModelConfigError(f"unknown model profile: {profile_id}")
            self._ensure_capabilities(
                profile,
                need_reasoning=need_reasoning,
                need_vision=need_vision,
                need_json=need_json,
                long_context=long_context,
            )
            return profile

        requirements = {
            "need_reasoning": need_reasoning,
            "need_vision": need_vision,
            "need_json": need_json,
            "long_context": long_context,
        }

        preferred_ids = self._preferred_profile_ids(requirements)
        for pid in preferred_ids:
            profile = self.store.by_id(pid)
            if profile and self._matches_requirements(profile, requirements):
                return profile

        for profile in self.store.all():
            if self._matches_requirements(profile, requirements):
                return profile

        missing = self._missing_capability_message(requirements)
        raise ModelConfigError(
            f"no model profile satisfies required capabilities ({missing}); "
            "add a matching profile in model_profiles.json"
        )

    def _preferred_profile_ids(self, requirements: dict[str, bool]) -> list[str]:
        """返回 default_routes 中按 key 出现顺序归约出引用到的所有 profile ID（去重）。

        调用方 select() 会对每个候选执行 _matches_requirements 过滤，
        因此该方法只需返回有优先级的候选 ID 列表——能力匹配由调用方负责。
        """
        seen: set[str] = set()
        result: list[str] = []
        for pid in self.store.default_routes.values():
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
        return result

    def _matches_requirements(
        self, profile: ModelProfile, requirements: dict[str, bool]
    ) -> bool:
        caps = profile.capabilities
        if requirements.get("need_reasoning") and not caps.reasoning:
            return False
        if requirements.get("need_vision") and not caps.vision:
            return False
        if requirements.get("need_json") and not caps.json_mode:
            return False
        if requirements.get("long_context") and not caps.long_context:
            return False
        return True

    def _ensure_capabilities(
        self,
        profile: ModelProfile,
        *,
        need_reasoning: bool,
        need_vision: bool,
        need_json: bool,
        long_context: bool,
    ) -> None:
        requirements = {
            "need_reasoning": need_reasoning,
            "need_vision": need_vision,
            "need_json": need_json,
            "long_context": long_context,
        }
        if not self._matches_requirements(profile, requirements):
            missing = self._missing_capability_message(requirements)
            raise ModelConfigError(
                f"profile {profile.id} does not satisfy required capabilities ({missing})"
            )

    @staticmethod
    def _missing_capability_message(requirements: dict[str, bool]) -> str:
        parts: list[str] = []
        for req_key, cap_attr in _CAPABILITY_CHECKS:
            if requirements.get(req_key):
                parts.append(cap_attr)
        return ", ".join(parts) if parts else "none"

    async def complete(
        self,
        profile: ModelProfile,
        messages: list[dict[str, Any]],
        *,
        max_tokens: int = 16,
        temperature: float | None = None,
        timeout: float | None = None,
        json_mode: bool = False,
    ) -> str:
        api_key = self.store.resolve_api_key(profile)
        base_url = self.store.resolve_base_url(profile)
        temp = temperature if temperature is not None else profile.default_temperature

        try:
            litellm = self._import_litellm()
        except ModelConfigError:
            raise
        except Exception as exc:
            raise ModelConfigError(
                "litellm is not available; install litellm to enable model calls"
            ) from exc

        call_timeout = timeout if timeout is not None else float(self.timeout_seconds)
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": f"{profile.provider}/{profile.model_name}",
                    "messages": messages,
                    "api_key": api_key,
                    "max_tokens": max_tokens,
                    "timeout": call_timeout,
                }
                if base_url:
                    kwargs["api_base"] = base_url
                if temp is not None:
                    kwargs["temperature"] = temp
                if profile.reasoning_effort is not None:
                    kwargs["reasoning_effort"] = profile.reasoning_effort
                if json_mode and profile.capabilities.json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = await asyncio.to_thread(litellm.completion, **kwargs)
                content = response.choices[0].message.content
                return content or ""
            except Exception as exc:
                # 认证/参数/资源不存在等永久性错误不重试，直接抛出
                try:
                    from litellm.exceptions import (
                        AuthenticationError,
                        BadRequestError,
                        InvalidRequestError,
                        NotFoundError,
                    )
                except ImportError:
                    AuthenticationError = BadRequestError = InvalidRequestError = NotFoundError = ()  # type: ignore[misc]
                if isinstance(
                    exc,
                    (AuthenticationError, BadRequestError, InvalidRequestError, NotFoundError),
                ):
                    raise ModelCallError(
                        f"model call failed for profile {profile.id}: request unsuccessful"
                    ) from exc
                last_error = exc
                logger.warning(
                    "model call attempt %s failed for profile %s",
                    attempt + 1,
                    profile.id,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))

        raise ModelCallError(
            f"model call failed for profile {profile.id}: request unsuccessful"
        ) from last_error

    @staticmethod
    def _import_litellm() -> Any:
        try:
            import litellm
        except ImportError as exc:
            raise ModelConfigError(
                "litellm is not installed; run pip install litellm"
            ) from exc
        litellm.suppress_debug_info = True
        return litellm

    async def test_profile(self, profile: ModelProfile) -> tuple[bool, str, int]:
        """最小真实请求验证连通性。"""
        started = time.perf_counter()
        try:
            content = await self.complete(
                profile,
                [{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            preview = (content or "").strip()[:32]
            return True, f"ok: {preview or 'empty response'}", latency_ms
        except ModelConfigError:
            raise
        except ModelCallError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return False, str(exc), latency_ms


@lru_cache
def get_model_gateway() -> ModelGateway:
    return ModelGateway(get_profile_store())


def reset_model_gateway_cache() -> None:
    if hasattr(get_model_gateway, "cache_clear"):
        get_model_gateway.cache_clear()
