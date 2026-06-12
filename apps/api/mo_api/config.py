"""应用配置。

所有配置来自环境变量 / .env，绝不在源码中硬编码密钥。
所有相对路径默认值均基于项目根目录解析，与 CWD 无关。
参见 docs/context/MO_Backend.md §3。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：本文件位于 apps/api/mo_api/config.py，向上 4 层即为仓库根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _root(rel: str) -> str:
    """将 ./ 开头的相对路径转为基于项目根的绝对路径."""
    if rel.startswith("./"):
        return str(_PROJECT_ROOT / rel[2:])
    return rel


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用基础
    app_env: str = "dev"
    api_base_url: str = "http://localhost:8000"

    # CORS：允许的前端来源（逗号分隔）
    cors_allow_origins: str = "http://localhost:5173"
    # CORS 正则：开发环境允许本机任意端口（Vite 端口漂移，如 5173→5174）
    # 生产环境可通过 env 置空以收紧来源
    cors_allow_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    # 存储（默认值经 _root() 基于项目根解析）
    database_url: str = "sqlite:///./runtime/mo.db"
    checkpoint_db_path: str = "./runtime/mo_checkpoints.db"
    execute_checkpoint_db_path: str = "./runtime/mo_execute_checkpoints.db"
    chroma_index_dir: str = "./runtime/indexes"
    paper_index_dir: str = "./runtime/indexes/paper"
    web_search_retriever: str = ""
    runtime_dir: str = "./runtime"

    # RepoDiscovery（F-015：GitHub Search API 自动发现热门相关仓库）
    repo_discovery_enabled: bool = True
    github_api_base_url: str = "https://api.github.com"
    # 仅存放环境变量名（token 本身从 env 读取，绝不硬编码）
    github_token_env: str = "GITHUB_TOKEN"
    repo_discovery_max_candidates: int = 15
    repo_discovery_per_query: int = 5
    repo_discovery_timeout_seconds: int = 15

    # RepoIngest（gitingest）
    repo_ingest_max_bytes: int = 50_000_000
    repo_ingest_exclude_patterns: str = (
        ".git,.env,node_modules,venv,__pycache__,*.pyc,*.bin,*.png,*.jpg"
    )
    repo_ingest_include_patterns: str = ""

    # 模型 profile 表路径（M5 ModelGateway 使用，此处仅声明）
    model_profiles_path: str = "./apps/api/model_profiles.json"
    model_call_timeout_seconds: int = 30
    model_call_max_retries: int = 2

    # 权限默认值（保守）
    default_allow_web_search: bool = False
    default_allow_repo_clone: bool = True
    default_allow_smoke_test: bool = False
    default_allow_dependency_install: bool = False

    # DemoMode（F-014）
    demo_mode: bool = False

    # Sandbox（R-004，默认关闭）
    sandbox_enabled: bool = False
    sandbox_command_whitelist: str = (
        "pytest,python -m pytest,python --version,pip --version"
    )
    sandbox_timeout_seconds: int = 120
    sandbox_workdir_base: str = "./runtime/repos"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def sandbox_whitelist_entries(self) -> list[str]:
        return [
            e.strip()
            for e in self.sandbox_command_whitelist.split(",")
            if e.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # 将相对路径默认值转为基于项目根的绝对路径（FIX-1）
    for field in (
        "database_url",
        "checkpoint_db_path",
        "execute_checkpoint_db_path",
        "chroma_index_dir",
        "paper_index_dir",
        "runtime_dir",
        "model_profiles_path",
        "sandbox_workdir_base",
    ):
        val = getattr(settings, field)
        if val.startswith("sqlite:///./"):
            # sqlite:///./runtime/mo.db → sqlite:///<root>/runtime/mo.db
            object.__setattr__(
                settings, field,
                "sqlite:///" + _root(val[10:]),
            )
        elif val and val.startswith("./"):
            object.__setattr__(settings, field, _root(val))
    return settings
