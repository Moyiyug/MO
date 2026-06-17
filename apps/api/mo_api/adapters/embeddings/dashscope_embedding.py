"""DashScope 多模态 Embedding 模型适配器。

实现 lmi.EmbeddingModel 接口，调用阿里云百炼 DashScope
Multimodal Embedding API（非 OpenAI 兼容端点）。

支持的模型：
- tongyi-embedding-vision-plus-2026-03-06（默认 1152 维，64-1152）
- tongyi-embedding-vision-flash（默认 768 维，64-768）

参考：https://help.aliyun.com/zh/model-studio/multimodal-embedding-api-reference
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from lmi import EmbeddingModel, EmbeddingModes
from pydantic import Field

logger = logging.getLogger("mo_api.dashscope_embedding")

# DashScope 多模态 Embedding API 端点
_DASHSCOPE_EMBEDDING_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "multimodal-embedding/multimodal-embedding"
)

# 各模型默认维度
_MODEL_DIMENSIONS: dict[str, int] = {
    "tongyi-embedding-vision-plus-2026-03-06": 1152,
    "tongyi-embedding-vision-plus": 1152,
    "tongyi-embedding-vision-flash": 768,
}


class DashScopeEmbeddingModel(EmbeddingModel):
    """DashScope 多模态 Embedding（仅文本输入，适配 paper-qa）。

    通过 httpx 直接调 DashScope REST API，不依赖 LiteLLM 路由。
    """

    name: str = "tongyi-embedding-vision-plus-2026-03-06"
    api_key: str = ""
    dimension: int | None = None
    max_text_length: int = 1024  # token 近似值，官方限制 1024 token
    _mode: EmbeddingModes = EmbeddingModes.DOCUMENT

    def set_mode(self, mode: EmbeddingModes) -> None:
        self._mode = mode

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """调用 DashScope API 生成文本向量。"""
        if not texts:
            return []

        api_key = self.api_key or self.config.get("api_key", "")
        if not api_key:
            raise ValueError("DashScope embedding requires QWEN_API_KEY")

        dimension = self.dimension or self.config.get(
            "dimension", _MODEL_DIMENSIONS.get(self.name, 1152)
        )
        batch_size = self.config.get("batch_size", 8)

        all_embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                truncated = [t[: self.max_text_length * 4] for t in batch]

                payload: dict[str, Any] = {
                    "model": self.name,
                    "input": {
                        "contents": [{"text": t} for t in truncated],
                    },
                    "parameters": {"dimension": dimension},
                }

                try:
                    response = await client.post(
                        _DASHSCOPE_EMBEDDING_URL,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPError as exc:
                    logger.error("DashScope embedding API error: %s", exc)
                    raise RuntimeError(
                        f"DashScope embedding request failed: {exc}"
                    ) from exc

                # 响应格式: {"output": {"embeddings": [{"embedding": [...], "index": 0}, ...]}}
                output = data.get("output", {})
                embeddings = output.get("embeddings", [])

                # 按 index 排序确保顺序
                embeddings.sort(key=lambda e: e.get("index", 0))
                for emb in embeddings:
                    vector = emb.get("embedding", [])
                    if vector:
                        all_embeddings.append([float(v) for v in vector])

                # 批间短暂延迟，避免限流
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)

        return all_embeddings
