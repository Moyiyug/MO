"""模型 profile 加载与存储（PRD F-012）。"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from ...config import get_settings
from ...models.model import ModelProfile, ModelProfilesConfig


class ModelConfigError(Exception):
    """模型配置错误（缺 profile / 缺能力 / 缺 key）。"""


def load_profiles(path: str | Path) -> ModelProfilesConfig:
    profile_path = Path(path)
    if not profile_path.is_file():
        raise ModelConfigError(
            "model profiles file not found; set MODEL_PROFILES_PATH or add model_profiles.json"
        )
    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
        return ModelProfilesConfig.model_validate(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ModelConfigError("invalid model profiles configuration") from exc


class ProfileStore:
    def __init__(self, config: ModelProfilesConfig) -> None:
        self._config = config
        self._by_id = {p.id: p for p in config.profiles}

    @property
    def default_routes(self) -> dict[str, str]:
        return dict(self._config.default_routes)

    def all(self) -> list[ModelProfile]:
        return list(self._config.profiles)

    def by_id(self, profile_id: str) -> ModelProfile | None:
        return self._by_id.get(profile_id)

    def has_api_key(self, profile: ModelProfile) -> bool:
        value = os.environ.get(profile.api_key_env, "").strip()
        return bool(value)

    def resolve_base_url(self, profile: ModelProfile) -> str | None:
        if profile.base_url:
            return profile.base_url
        if profile.base_url_env:
            return os.environ.get(profile.base_url_env, "").strip() or None
        return None

    def resolve_api_key(self, profile: ModelProfile) -> str:
        key = os.environ.get(profile.api_key_env, "").strip()
        if not key:
            raise ModelConfigError(
                f"API key not configured: set environment variable {profile.api_key_env}"
            )
        return key


@lru_cache
def get_profile_store() -> ProfileStore:
    settings = get_settings()
    config = load_profiles(settings.model_profiles_path)
    return ProfileStore(config)


def reset_profiles_cache() -> None:
    if hasattr(get_profile_store, "cache_clear"):
        get_profile_store.cache_clear()
