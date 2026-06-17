"""执行前前置检查服务（F-005）。

在执行任务前验证必需的模型能力、API 密钥、外部工具是否就绪，
避免执行到中途才因配置缺失而失败。
"""

from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger("mo_api.preflight")

from ..adapters.model_gateway.gateway import ModelGateway, ModelConfigError
from ..adapters.model_gateway.profiles import ProfileStore


class PreflightError(Exception):
    """前置检查失败。"""


class PreflightService:
    def __init__(self, gateway: ModelGateway, store: ProfileStore) -> None:
        self.gateway = gateway
        self.store = store

    def check_required_model_profiles(self) -> list[str]:
        """检查执行所需的最起码模型能力是否已配置且 API 密钥已设置。"""
        errors: list[str] = []

        checks: list[dict] = [
            {"need_reasoning": True, "need_json": True},
            {"need_json": True},
        ]
        for req in checks:
            try:
                profile = self.gateway.select(**req)
            except ModelConfigError as exc:
                errors.append(f"缺少能力配置文件 {req}: {exc}")
                continue
            if not self.store.has_api_key(profile):
                errors.append(
                    f"缺少 API 密钥：请设置环境变量 {profile.api_key_env}"
                )
        return errors

    async def check_git_available(self) -> str | None:
        """检查 git 是否可用。返回错误信息或 None。

        使用 subprocess.run 而非 asyncio.create_subprocess_exec，
        以兼容所有平台的 asyncio 事件循环。
        """
        import asyncio

        git_path = shutil.which("git")
        if git_path is None:
            return "未找到 git。请安装 Git（https://git-scm.com/）并确保其在 PATH 中。"

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [git_path, "--version"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace").strip()
                return f"git 不可用：{err or f'退出码 {result.returncode}'}"
            version = result.stdout.decode(errors="replace").strip()
            logger.info("git version: %s", version)
            return None
        except FileNotFoundError:
            return "未找到 git。请安装 Git（https://git-scm.com/）并确保其在 PATH 中。"
        except Exception as exc:
            return f"无法检查 git 可用性：{type(exc).__name__}: {exc}"
