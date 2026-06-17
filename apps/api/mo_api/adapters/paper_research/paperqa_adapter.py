"""paper-qa 适配器（MO_Backend §7.3）。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("mo_api.paperqa")

from ...adapters.embeddings.dashscope_embedding import DashScopeEmbeddingModel
from ...adapters.model_gateway.gateway import ModelGateway, get_model_gateway
from ...adapters.model_gateway.profiles import get_profile_store
from ...config import get_settings
from .base import PaperAnswer, PaperContext, PaperResearchAdapter, PaperResearchError


# ── DeepSeek V4 模型元数据 ────────────────────────────────────────────────
# deepseek-v4-pro / deepseek-v4-flash 于 2026-04-24 上线，
# 当前 LiteLLM 本地备份尚不含这两个模型；注册到 model_cost 确保
# paper-qa (via lmi → litellm.model_cost) 与 ModelGateway.litellm.completion()
# 都能正确获取上下文窗口等元数据。
# 来源: https://api-docs.deepseek.com/quick_start/pricing

_DEEPSEEK_V4_MODEL_COST = {
    "deepseek/deepseek-v4-pro": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "max_tokens": 1_000_000,
        "input_cost_per_token": 4.35e-7,
        "output_cost_per_token": 8.7e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
    "deepseek/deepseek-v4-flash": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "max_tokens": 1_000_000,
        "input_cost_per_token": 1.4e-7,
        "output_cost_per_token": 2.8e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
    # 无 provider 前缀的别名（LiteLLM 内部查找也以这些 key 为准）
    "deepseek-v4-pro": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "max_tokens": 1_000_000,
        "input_cost_per_token": 4.35e-7,
        "output_cost_per_token": 8.7e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
    "deepseek-v4-flash": {
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "max_tokens": 1_000_000,
        "input_cost_per_token": 1.4e-7,
        "output_cost_per_token": 2.8e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
}

_DEEPSEEK_V4_MODEL_INFO = {
    "deepseek-v4-pro": {
        "mode": "chat",
        "max_tokens": 1_000_000,
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "input_cost_per_token": 4.35e-7,
        "output_cost_per_token": 8.7e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
    "deepseek-v4-flash": {
        "mode": "chat",
        "max_tokens": 1_000_000,
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 384_000,
        "input_cost_per_token": 1.4e-7,
        "output_cost_per_token": 2.8e-7,
        "supports_function_calling": True,
        "supports_parallel_function_calling": True,
        "supports_vision": False,
    },
}


def _register_deepseek_v4_models() -> None:
    """将 deepseek-v4-pro / v4-flash 注册到 LiteLLM 模型元数据库中。

    幂等：重复调用不报错。仅在新模型不在库中时写入。
    """
    try:
        import litellm
    except ImportError:
        return

    # 注册到 litellm.model_cost（paper-qa / lmi 的 max_input_tokens 查询入口）
    for key, info in _DEEPSEEK_V4_MODEL_COST.items():
        if key not in litellm.model_cost:
            litellm.model_cost[key] = info  # type: ignore[index]

    # 注册到 litellm.model_info（litellm 内部的 get_model_info 使用）
    if hasattr(litellm, "model_info"):
        for key, info in _DEEPSEEK_V4_MODEL_INFO.items():
            if key not in litellm.model_info:
                litellm.model_info[key] = info  # type: ignore[index]


def _sanitize_error(message: str) -> str:
    text = message or "paper research failed"
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


class PaperQAAdapter(PaperResearchAdapter):
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway
        self._embedding_model: DashScopeEmbeddingModel | None = None

    def _ensure_gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    def _llm_model_string(self) -> str:
        """返回 LiteLLM 兼容的 provider/model 字符串。

        model_profiles.json 中的 model_name（如 deepseek-v4-pro）已经是
        DeepSeek API 原生模型名，与 provider 拼接后即为 LiteLLM 可用的格式。
        """
        profile = self._ensure_gateway().select(need_reasoning=True, need_json=True)
        # 确保新模型在 LiteLLM 元数据库中注册
        _register_deepseek_v4_models()
        return f"{profile.provider}/{profile.model_name}"

    def _resolve_embedding_model(self) -> DashScopeEmbeddingModel | None:
        """从 model_profiles.json 的 default_routes.embedding 解析嵌入模型。

        查找 ID 为 default_routes["embedding"] 的 profile，
        读取 api_key_env / model_name，构造 DashScopeEmbeddingModel。
        找不到或缺少 API key 时返回 None。
        """
        if self._embedding_model is not None:
            return self._embedding_model

        try:
            store = get_profile_store()
            embedding_id = store.default_routes.get("embedding", "")
            if not embedding_id:
                logger.info("No embedding route configured in default_routes")
                return None

            profile = store.by_id(embedding_id)
            if profile is None:
                logger.warning("Embedding profile %s not found", embedding_id)
                return None

            api_key = store.resolve_api_key(profile)
            if not api_key:
                logger.warning(
                    "Embedding API key not set: %s (env: %s)",
                    embedding_id,
                    profile.api_key_env,
                )
                return None

            dimension = None
            meta = getattr(profile, "_meta", None) or {}
            if isinstance(meta, dict):
                dimension = meta.get("dimension")

            self._embedding_model = DashScopeEmbeddingModel(
                name=profile.model_name,
                api_key=api_key,
                dimension=dimension,
            )
            logger.info(
                "Resolved embedding model: %s (dim=%s)",
                profile.model_name,
                self._embedding_model.dimension,
            )
        except Exception as exc:
            logger.warning("Failed to resolve embedding model: %s", exc)

        return self._embedding_model

    def _build_llm_config(self, llm_str: str) -> dict[str, Any]:
        """构建 paper-qa llm_config，显式传入 max_input_tokens。

        对 deepseek-v4 系列模型提供 1M 上下文窗口，绕过 LiteLLM 本地备份
        缺失该模型元数据的问题。对其他模型返回空配置（由 lmi/litellm 自行查询）。
        """
        model_name = llm_str.split("/", 1)[-1] if "/" in llm_str else llm_str
        if "deepseek-v4" in model_name.lower():
            return {"max_input_tokens": 1_000_000, "max_output_tokens": 384_000}
        return {}

    async def query_papers(
        self,
        doc_paths: list[str],
        question: str,
        *,
        task_id: str,
    ) -> PaperAnswer:
        if not doc_paths:
            return PaperAnswer(answer="", contexts=[])

        try:
            from paperqa import Docs, Settings
        except ImportError as exc:
            raise PaperResearchError(
                "paper-qa is not installed; add paper-qa to requirements"
            ) from exc

        # 确保 DeepSeek V4 模型在 LiteLLM 中已注册
        _register_deepseek_v4_models()

        settings = get_settings()
        index_dir = Path(settings.paper_index_dir) / task_id
        index_dir.mkdir(parents=True, exist_ok=True)

        llm = self._llm_model_string()
        llm_config = self._build_llm_config(llm)

        # 解析嵌入模型：优先 Qwen DashScope embedding，
        # 不可用时回退 sparse（关键词检索），不阻塞主流程。
        embedding_model = self._resolve_embedding_model()
        if embedding_model is not None:
            pqa_embedding = llm  # 占位；实际 embedding_model 直接传入 aadd/aquery
        else:
            pqa_embedding = "sparse"  # 无 QWEN_API_KEY 时回退关键词检索

        pqa_settings = Settings(
            llm=llm,
            summary_llm=llm,
            embedding=pqa_embedding,
            llm_config=llm_config if llm_config else None,
            summary_llm_config=llm_config if llm_config else None,
        )

        docs = Docs()
        failed = 0
        for path in doc_paths:
            try:
                await docs.aadd(
                    path,
                    settings=pqa_settings,
                    embedding_model=embedding_model,
                )
            except Exception as exc:
                logger.warning("paperqa aadd failed for %s: %s", path, exc)
                failed += 1

        if failed == len(doc_paths):
            return PaperAnswer(answer="", contexts=[])

        try:
            session = await docs.aquery(
                question,
                settings=pqa_settings,
                embedding_model=embedding_model,
            )
        except Exception as exc:
            raise PaperResearchError(_sanitize_error(str(exc))) from exc

        contexts: list[PaperContext] = []
        for ctx in getattr(session, "contexts", []) or []:
            raw = getattr(ctx, "text", "") or str(ctx)
            # paper-qa >= 5.x: Context.text 可能返回 Text 对象而非 str
            text = str(raw.text) if hasattr(raw, "text") and not isinstance(raw, str) else str(raw)
            name = getattr(ctx, "name", "") or getattr(ctx, "docname", "unknown")
            contexts.append(
                PaperContext(
                    text=text[:2000],
                    source_name=str(name),
                    locator=str(name),
                )
            )

        answer = getattr(session, "answer", "") or ""
        return PaperAnswer(answer=str(answer), contexts=contexts)
