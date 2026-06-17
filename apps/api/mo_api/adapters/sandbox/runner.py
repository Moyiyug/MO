"""沙箱命令执行器（R-004）：白名单 + 限目录 + 超时 + 非 shell subprocess。"""

from __future__ import annotations

import asyncio
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from ...config import Settings, get_settings
from ...models.sandbox import SandboxRunResult

_SHELL_METACHAR_RE = re.compile(r"[;&|><`]")


class SandboxGuardError(ValueError):
    """命令或工作目录未通过沙箱守卫。"""


class SandboxRunner:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._output_limit = 8000

    def _base_dir(self) -> Path:
        return Path(self.settings.sandbox_workdir_base).resolve()

    @staticmethod
    def repo_slug(repo_url: str) -> str:
        """从 repo URL 提取目录名。"""
        return repo_url.rstrip("/").split("/")[-1] or "repo"

    def resolve_workdir(self, task_id: str, repo_url: str) -> Path:
        """解析并创建任务/仓库隔离工作目录。"""
        slug = self.repo_slug(repo_url)
        workdir = self._base_dir() / task_id / slug
        workdir.mkdir(parents=True, exist_ok=True)
        return workdir.resolve()

    def guard(self, command: str, cwd: Path) -> None:
        """校验命令白名单与工作目录边界。"""
        cmd = command.strip()
        if not cmd:
            raise SandboxGuardError("empty command")
        if _SHELL_METACHAR_RE.search(cmd):
            raise SandboxGuardError("shell metacharacters are not allowed")

        allowed = False
        for entry in self.settings.sandbox_whitelist_entries:
            if cmd == entry or cmd.startswith(entry + " "):
                allowed = True
                break
        if not allowed:
            raise SandboxGuardError(f"command not in whitelist: {cmd}")

        base = self._base_dir()
        resolved_cwd = cwd.resolve()
        try:
            resolved_cwd.relative_to(base)
        except ValueError as exc:
            raise SandboxGuardError("working directory outside sandbox base") from exc

    def _parse_args(self, command: str) -> list[str]:
        return shlex.split(command, posix=False)

    async def run(self, command: str, cwd: Path) -> SandboxRunResult:
        """在守卫通过后执行命令。

        使用 subprocess.Popen + asyncio.to_thread 替代 create_subprocess_exec，
        以兼容所有平台的 asyncio 事件循环。
        """
        cmd = command.strip()
        try:
            self.guard(cmd, cwd)
        except SandboxGuardError as exc:
            return SandboxRunResult(
                command=cmd,
                cwd=str(cwd),
                guard_rejected=True,
                guard_reason=str(exc),
            )

        args = self._parse_args(cmd)
        if not args:
            return SandboxRunResult(
                command=cmd,
                cwd=str(cwd),
                guard_rejected=True,
                guard_reason="empty argv",
            )

        # 解析可执行文件完整路径，避免 Windows PATH 查找问题
        resolved = shutil.which(args[0])
        if resolved:
            args[0] = resolved

        timeout = self.settings.sandbox_timeout_seconds
        start = time.monotonic()

        def _execute():
            proc = subprocess.Popen(
                args,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = proc.communicate(timeout=timeout)
                return proc, stdout_b, stderr_b, False
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_b, stderr_b = proc.communicate()
                return proc, stdout_b, stderr_b, True

        proc, stdout_b, stderr_b, timed_out = await asyncio.to_thread(_execute)

        duration = time.monotonic() - start
        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        stderr = (stderr_b or b"").decode("utf-8", errors="replace")

        return SandboxRunResult(
            command=cmd,
            cwd=str(cwd),
            exit_code=proc.returncode,
            stdout_tail=stdout[-self._output_limit:],
            stderr_tail=stderr[-self._output_limit:],
            duration_seconds=round(duration, 3),
            timed_out=timed_out,
        )
