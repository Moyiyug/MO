"""repo_ingest 节点：克隆/摄取仓库并构建 RepoCard。"""

from __future__ import annotations

import logging
import traceback as _tb

from langgraph.types import interrupt

logger = logging.getLogger("mo_api.repo_ingest")

from ...agents.repo_card import build_repo_card
from ...models.enums import NodeStatus
from sqlmodel import Session

from ...storage import db
from ...storage.repositories import RepoCardRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..state import MOState

NODE_ID = "repo_ingest"


async def repo_ingest(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)
    permissions = state.get("permissions") or {}

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

    if not permissions.get("allow_repo_clone", True):
        decision = interrupt(
            {
                "action": "repo_clone",
                "requires_approval": True,
                "node": NODE_ID,
            }
        )
        if not decision.get("approved"):
            await publish_node_event(
                ctx,
                NODE_ID,
                NodeStatus.FAILED,
                error_message="仓库克隆未获批准",
                logs=["repo clone rejected by user"],
            )
            errors = list(state.get("errors") or [])
            errors.append({"node": NODE_ID, "msg": "clone not approved"})
            return {"errors": errors}

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="正在摄取仓库",
        logs=["repo ingest started"],
    )

    repo_cards = list(state.get("repo_cards") or [])
    evidence_items = list(state.get("evidence_items") or [])
    ingested_repos = list(state.get("ingested_repos") or [])
    errors = list(state.get("errors") or [])
    all_evidence_ids: list[str] = []
    vector_store = ctx.vector_store_factory(task_id)

    for repo_url in state.get("repo_urls") or []:
        if repo_url in ingested_repos:
            continue

        with Session(db.get_engine()) as session:
            if RepoCardRepository(session).exists_for_repo(task_id, repo_url):
                ingested_repos.append(repo_url)
                continue

        try:
            digest = await ctx.repo_adapter.ingest(repo_url)
            await vector_store.add_chunks(digest.content, source_uri=digest.source_uri)

            card = await build_repo_card(
                task_id,
                digest,
                ctx.model_gateway,
                ctx.evidence_service,
            )

            with Session(db.get_engine()) as session:
                RepoCardRepository(session).create(card)

            ingested_repos.append(repo_url)
            repo_cards.append(card.model_dump(mode="json"))
            all_evidence_ids.extend(card.evidence_ids)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}".strip()
            if not detail or detail == f"{type(exc).__name__}:":
                detail = f"{type(exc).__name__}（无详细消息）"
            errors.append(
                {"node": NODE_ID, "repo": repo_url, "msg": detail[:200]}
            )
            logger.warning(
                "repo ingest failed for %s: %s\n%s",
                repo_url, detail, _tb.format_exc(),
            )
            await publish_node_event(
                ctx,
                NODE_ID,
                NodeStatus.RUNNING,
                logs=[f"repo ingest failed for {repo_url}: {detail}"],
            )

    # 从 DB 重建 evidence_items（避免 state 累积重复）
    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    repo_urls = list(state.get("repo_urls") or [])
    if repo_urls and not repo_cards:
        summary = (
            errors[-1].get("msg", "all repositories failed to ingest")
            if errors
            else "no repository content ingested"
        )
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.FAILED,
            error_message=summary[:200],
            logs=[f"repo ingest failed: {summary}"],
        )
        raise RuntimeError(summary)

    result: MOState = {
        "repo_cards": repo_cards,
        "evidence_items": evidence_items,
        "ingested_repos": ingested_repos,
    }
    if errors:
        result["errors"] = errors
    return result
