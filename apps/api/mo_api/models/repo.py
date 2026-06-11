"""仓库调研领域模型（PRD F-004）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoDigest(BaseModel):
    """gitingest 原始产出。"""

    summary: str
    tree: str
    content: dict[str, str] = Field(default_factory=dict)
    source_uri: str


class RepoCard(BaseModel):
    """仓库卡片（PRD F-004）。"""

    id: str
    task_id: str
    repo_url: str
    repo_name: str
    summary: str
    primary_language: str | None = None
    project_type: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    docs_paths: list[str] = Field(default_factory=list)
    license: str | None = None
    risks: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    field_labels: dict[str, str] = Field(default_factory=dict)
