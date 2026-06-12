"""repo_discovery 节点（PRD F-015）：研究目标 -> 关键词 -> GitHub 搜索 -> 相关性重排。

仅取仓库元数据（低成本、不克隆），产出 RepoCandidate 候选清单写入图状态，
随后在 PlanMode 中由用户确认（R-001/R-002）。所有外部调用失败均降级，
不让 PlanMode 因发现失败而硬中断。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re

from ...adapters.model_gateway.gateway import ModelGateway, get_model_gateway
from ...adapters.repo_discovery import (
    RepoDiscoveryAdapter,
    RepoDiscoveryError,
    get_repo_discovery_adapter,
)
from ...config import get_settings
from ...models.repo_discovery import RepoCandidate
from ..state import MOState

logger = logging.getLogger("mo_api.repo_discovery")

NODE_ID = "repo_discovery"


def _name_from_url(url: str) -> str:
    m = re.search(r"github\.com/([^/]+/[^/?#]+)", url)
    if m:
        return m.group(1).removesuffix(".git")
    return url


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def _generate_queries(goal: str, gateway: ModelGateway) -> list[str]:
    """用 LLM 把研究目标拆成 3-5 个 GitHub 搜索查询；失败则回退为目标文本。"""
    fallback = [goal.strip()[:120]] if goal.strip() else []
    try:
        profile = gateway.select(need_json=True)
    except Exception:  # noqa: BLE001 - 无可用模型时降级
        try:
            profile = gateway.select()
        except Exception:  # noqa: BLE001
            return fallback

    prompt = (
        "You generate GitHub repository search queries for a research goal.\n"
        "Return ONLY a JSON array of 3-5 short English keyword queries "
        '(no owner/repo, just topic keywords), e.g. ["llm agent framework", "rag pipeline"].\n\n'
        f"Research goal: {goal}"
    )
    try:
        raw = await gateway.complete(
            profile,
            [{"role": "user", "content": prompt}],
            max_tokens=256,
        )
    except Exception:  # noqa: BLE001 - 模型不可用/调用失败 -> 降级
        logger.debug("query generation failed; falling back to goal text")
        return fallback

    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            queries = [str(q).strip() for q in data if str(q).strip()]
            if queries:
                return queries[:5]
    except json.JSONDecodeError:
        # 退而求其次：从文本中抽取引号内的关键词
        quoted = re.findall(r'"([^"]+)"', text)
        if quoted:
            return quoted[:5]
    return fallback


async def _rerank(
    goal: str, candidates: list[RepoCandidate], gateway: ModelGateway
) -> None:
    """用 LLM 给候选打相关性分；失败则按 stars 归一化兜底。原地修改 candidates。"""
    if not candidates:
        return

    def _stars_fallback() -> None:
        max_stars = max((c.stars for c in candidates), default=0) or 1
        for c in candidates:
            c.relevance_score = round(min(1.0, c.stars / max_stars), 3)
            if not c.relevance_reason:
                c.relevance_reason = "按 stars 热度排序（未启用模型相关性评估）"

    try:
        profile = gateway.select(need_json=True)
    except Exception:  # noqa: BLE001
        try:
            profile = gateway.select()
        except Exception:  # noqa: BLE001
            _stars_fallback()
            return

    listing = "\n".join(
        f"{i}. {c.repo_name} (stars={c.stars}, lang={c.language or 'n/a'}): "
        f"{(c.description or '')[:160]}"
        for i, c in enumerate(candidates)
    )
    prompt = (
        "Rate each repository's relevance to the research goal from 0 to 1.\n"
        'Return ONLY a JSON array like [{"index":0,"score":0.9,"reason":"..."}].\n\n'
        f"Research goal: {goal}\n\nRepositories:\n{listing}"
    )
    try:
        raw = await gateway.complete(
            profile,
            [{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
    except Exception:  # noqa: BLE001
        _stars_fallback()
        return

    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _stars_fallback()
        return

    if not isinstance(data, list):
        _stars_fallback()
        return

    applied = False
    for entry in data:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
            continue
        try:
            score = float(entry.get("score", 0.0))
        except (TypeError, ValueError):
            continue
        candidates[idx].relevance_score = max(0.0, min(1.0, score))
        candidates[idx].relevance_reason = str(entry.get("reason", ""))[:300]
        applied = True

    if not applied:
        _stars_fallback()


def _merge_seeds_and_selection(
    discovered: list[RepoCandidate], repo_urls: list[str]
) -> list[RepoCandidate]:
    """合并已发现候选与用户种子/已选仓库；已选项置顶。"""
    by_url: dict[str, RepoCandidate] = {c.repo_url: c for c in discovered}
    for url in repo_urls:
        url = url.strip()
        if not url:
            continue
        if url in by_url:
            by_url[url].selected = True
        else:
            by_url[url] = RepoCandidate(
                repo_url=url,
                repo_name=_name_from_url(url),
                relevance_score=1.0,
                relevance_reason="用户提供的种子仓库",
                selected=True,
                discovered_by="user_seed",
            )
    merged = list(by_url.values())
    merged.sort(key=lambda c: (not c.selected, -c.relevance_score, -c.stars))
    return merged


async def discover_candidates(
    goal: str,
    repo_urls: list[str],
    *,
    adapter: RepoDiscoveryAdapter,
    gateway: ModelGateway,
) -> tuple[list[RepoCandidate], str | None]:
    """核心发现流程（可注入 adapter/gateway，便于单测）。"""
    settings = get_settings()
    note: str | None = None
    discovered: list[RepoCandidate] = []

    # DemoMode：离线返回预烤候选，保证无网络也能演示自动发现（F-014）
    if getattr(settings, "demo_mode", False):
        from ...demo.fixtures import build_demo_repo_candidates

        discovered = build_demo_repo_candidates()
        merged = _merge_seeds_and_selection(discovered, repo_urls)
        return merged, "DemoMode：使用离线预烤候选仓库。"

    if settings.repo_discovery_enabled and goal.strip():
        queries = await _generate_queries(goal, gateway)
        try:
            discovered = await adapter.search(
                queries,
                per_query=settings.repo_discovery_per_query,
                limit=settings.repo_discovery_max_candidates,
            )
        except RepoDiscoveryError as exc:
            note = f"自动发现失败，已降级：{exc}"
            logger.warning("repo discovery failed: %s", exc)
            discovered = []
        if discovered:
            await _rerank(goal, discovered, gateway)
            discovered.sort(key=lambda c: c.relevance_score, reverse=True)
    elif not settings.repo_discovery_enabled:
        note = "自动发现已禁用（REPO_DISCOVERY_ENABLED=false），仅使用用户提供的仓库。"

    merged = _merge_seeds_and_selection(discovered, repo_urls)
    if not merged and not note:
        note = "未发现相关仓库，请在创建任务时补充仓库 URL 或调整研究目标。"
    return merged, note


def _run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # 极少数情况下已处于事件循环中：在独立线程运行，避免嵌套循环报错
    if loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)


def repo_discovery(state: MOState) -> MOState:
    """PlanMode 同步节点：调用异步发现流程，把候选写入图状态。"""
    goal = state.get("goal", "") or ""
    repo_urls = list(state.get("repo_urls") or [])

    adapter = get_repo_discovery_adapter()
    gateway = get_model_gateway()

    candidates, note = _run_sync(
        discover_candidates(goal, repo_urls, adapter=adapter, gateway=gateway)
    )

    update: MOState = {
        "repo_candidates": [c.model_dump(mode="json") for c in candidates]
    }
    if note:
        errors = list(state.get("errors") or [])
        errors.append({"node": NODE_ID, "message": note})
        update["errors"] = errors
    return update
