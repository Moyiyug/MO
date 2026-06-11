"""ModelGateway 数据模型（PRD F-012）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelCapability(BaseModel):
    text: bool = True
    reasoning: bool = False
    vision: bool = False
    video: bool = False
    tool_calling: bool = False
    json_mode: bool = False
    long_context: bool = False


class ModelProfile(BaseModel):
    id: str
    provider: str
    model_name: str
    api_key_env: str
    base_url_env: str | None = None
    base_url: str | None = None
    capabilities: ModelCapability
    default_temperature: float | None = None
    reasoning_effort: str | None = None  # "low" | "medium" | "high" — 仅 deepseek thinking 模式


class ModelProfilesConfig(BaseModel):
    profiles: list[ModelProfile]
    default_routes: dict[str, str] = Field(default_factory=dict)


class ModelProfilePublic(BaseModel):
    """对外暴露的 profile — 绝不包含 key 或 base_url 敏感值。"""

    id: str
    provider: str
    model_name: str
    capabilities: ModelCapability
    has_api_key: bool
    default_temperature: float | None = None


class ModelCapabilitiesResponse(BaseModel):
    profiles: list[ModelProfilePublic]
    default_routes: dict[str, str]


class ModelTestRequest(BaseModel):
    profile_id: str | None = None
    need_reasoning: bool = False
    need_vision: bool = False
    need_json: bool = False
    long_context: bool = False


class ModelTestResponse(BaseModel):
    ok: bool
    profile_id: str
    latency_ms: int | None = None
    message: str
