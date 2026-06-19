"""Task 相关的 API / 领域模型（Pydantic）。

对应 PRD F-001（TaskCreate）、§5（API 契约）。
M1 最小范围：权限、创建请求、响应。校验委托 models/validators.py。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .enums import OutputLanguage, TaskStatus
from .validators import RepoUrlError, validate_repo_urls


class TaskPermissions(BaseModel):
    """任务权限开关（PRD F-001）。默认保守。"""

    allow_web_search: bool = False
    allow_repo_clone: bool = True
    allow_smoke_test: bool = False
    allow_dependency_install: bool = False
    has_gpu: bool = False
    max_runtime_minutes: int = Field(default=30, ge=1, le=24 * 60)


class TaskCreateRequest(BaseModel):
    """创建任务请求体（PRD F-001）。

    repo_urls 可选（0-5 个）：留空时由 RepoDiscovery 自动发现热门相关仓库（F-015）；
    也可填 1-5 个种子仓库作为补充。
    """

    goal: str = Field(min_length=1, max_length=4000)
    repo_urls: list[str] = Field(default_factory=list, max_length=5)
    paper_urls: list[str] = Field(default_factory=list)
    output_language: OutputLanguage = OutputLanguage.ZH
    template: str | None = None
    permissions: TaskPermissions = Field(default_factory=TaskPermissions)

    @field_validator("repo_urls")
    @classmethod
    def _check_repo_urls(cls, v: list[str]) -> list[str]:
        try:
            return validate_repo_urls(v)
        except RepoUrlError as exc:
            raise ValueError(str(exc)) from exc


class TaskResponse(BaseModel):
    """任务详情响应（PRD §5）。"""

    task_id: str
    goal: str
    status: TaskStatus
    repo_urls: list[str]
    paper_urls: list[str]
    output_language: OutputLanguage
    template: str | None = None
    permissions: TaskPermissions
    created_at: datetime


class TaskCreateResponse(BaseModel):
    """创建任务响应（PRD F-001：返回 task_id + status=PLANNING）。"""

    task_id: str
    status: TaskStatus


class TaskPageResponse(BaseModel):
    """分页历史任务响应（F-013）。"""

    items: list[TaskResponse]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class TaskBulkDeleteResponse(BaseModel):
    """批量删除历史任务响应（F-013）。

    EXECUTING 任务不会被删除，直到未来实现取消执行能力。
    """

    deleted_task_ids: list[str] = Field(default_factory=list)
    skipped_task_ids: list[str] = Field(default_factory=list)
