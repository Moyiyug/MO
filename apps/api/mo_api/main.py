"""FastAPI 应用入口。

装配：CORS、lifespan(init_db)、统一异常处理、路由注册。
异常响应不泄露 key / 绝对路径 / 堆栈 / token（参见 mo-backend 规则）。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routers import plans, tasks
from .storage.db import init_db

logger = logging.getLogger("mo_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MO API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        # jsonable_encoder 安全处理 errors 中的 ctx（可能含异常对象）
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {"error": "validation_error", "detail": exc.errors()}
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        # 记录完整堆栈到服务端日志，但对外只返回通用信息（不泄密）
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "detail": "internal server error"},
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(tasks.router)
    app.include_router(plans.router)
    return app


app = create_app()
