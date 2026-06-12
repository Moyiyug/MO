"""沙箱执行模型（R-004）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SandboxRunRequest(BaseModel):
    """沙箱单次命令执行请求。"""

    command: str = Field(min_length=1, max_length=2000)
    cwd: str = Field(min_length=1, max_length=2000)


class SandboxRunResult(BaseModel):
    """沙箱命令执行结果。"""

    command: str
    cwd: str
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    guard_rejected: bool = False
    guard_reason: str | None = None
