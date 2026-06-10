"""数据库引擎与会话管理。

MVP 使用 SQLite。engine 在首次访问时按配置创建（lru_cache 单例），
便于测试通过覆盖 get_session 依赖注入临时库。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from ..config import get_settings

# 确保表模型在 create_all 之前被导入注册
from . import tables as _tables  # noqa: F401


def _ensure_sqlite_dir(database_url: str) -> None:
    """对 sqlite 文件库，确保其所在目录存在。"""
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        path = database_url[len(prefix):]
        if path and path != ":memory:":
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    database_url = settings.database_url
    _ensure_sqlite_dir(database_url)
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(database_url, connect_args=connect_args)


def init_db() -> None:
    """创建所有表（幂等）。"""
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话。"""
    with Session(get_engine()) as session:
        yield session
