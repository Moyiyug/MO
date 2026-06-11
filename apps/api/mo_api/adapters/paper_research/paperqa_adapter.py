"""paper-qa 适配器（MO_Backend §7.3）。"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("mo_api.paperqa")

from ...adapters.model_gateway.gateway import ModelGateway, get_model_gateway
from ...config import get_settings
from .base import PaperAnswer, PaperContext, PaperResearchAdapter, PaperResearchError


def _sanitize_error(message: str) -> str:
    text = message or "paper research failed"
    text = re.sub(r"ghp_[A-Za-z0-9]+", "[REDACTED]", text)
    text = re.sub(r"(?i)(token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:500]


class PaperQAAdapter(PaperResearchAdapter):
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway

    def _ensure_gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    def _llm_model_string(self) -> str:
        profile = self._ensure_gateway().select(need_reasoning=True, need_json=True)
        # paper-qa 通过 LiteLLM；返回 provider/model 格式供其识别
        # 注意：不设置全局环境变量（避免多任务并发污染），
        # LiteLLM 会从常规环境变量（OPENAI_API_KEY 等）读取凭据
        return f"{profile.provider}/{profile.model_name}"

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

        settings = get_settings()
        index_dir = Path(settings.paper_index_dir) / task_id
        index_dir.mkdir(parents=True, exist_ok=True)

        llm = self._llm_model_string()
        pqa_settings = Settings(llm=llm, summary_llm=llm, embedding=llm)

        docs = Docs()
        failed = 0
        for path in doc_paths:
            try:
                await docs.aadd(path, settings=pqa_settings)
            except Exception as exc:
                logger.warning("paperqa aadd failed for %s: %s", path, exc)
                failed += 1

        if failed == len(doc_paths):
            return PaperAnswer(answer="", contexts=[])

        try:
            session = await docs.aquery(question, settings=pqa_settings)
        except Exception as exc:
            raise PaperResearchError(_sanitize_error(str(exc))) from exc

        contexts: list[PaperContext] = []
        for ctx in getattr(session, "contexts", []) or []:
            text = getattr(ctx, "text", "") or str(ctx)
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
