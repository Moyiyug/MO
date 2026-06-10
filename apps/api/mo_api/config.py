"""应用配置。

所有配置来自环境变量 / .env，绝不在源码中硬编码密钥。
参见 docs/context/MO_Backend.md §3。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用基础
    app_env: str = "dev"
    api_base_url: str = "http://localhost:8000"

    # CORS：允许的前端来源（逗号分隔）
    cors_allow_origins: str = "http://localhost:5173"

    # 存储
    database_url: str = "sqlite:///./runtime/mo.db"
    checkpoint_db_path: str = "./runtime/mo_checkpoints.db"
    runtime_dir: str = "./runtime"

    # 模型 profile 表路径（M5 ModelGateway 使用，此处仅声明）
    model_profiles_path: str = "./apps/api/model_profiles.json"

    # 权限默认值（保守）
    default_allow_web_search: bool = False
    default_allow_repo_clone: bool = True
    default_allow_smoke_test: bool = False
    default_allow_dependency_install: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
