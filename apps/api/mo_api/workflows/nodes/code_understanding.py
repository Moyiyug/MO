"""code_understanding 节点：向量检索 + LLM 代码理解。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from ...models.enums import (
    CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX,
    CODE_INSIGHT_LOCATOR_EXECUTION_PATH,
    CODE_INSIGHT_LOCATOR_REPO_SUMMARY,
    CODE_INSIGHT_PREFIX_CORE_MODULE,
    ClaimLabel,
    EvidenceStrength,
    NodeStatus,
    SourceType,
)
from ...models.evidence import EvidenceItem
from ..execute_context import get_context, publish_node_event
from ..state import MOState

NODE_ID = "code_understanding"


def _parse_insights(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {
        "core_modules": re.findall(r'"core_modules"\s*:\s*\[(.*?)\]', text, re.DOTALL),
        "execution_path": "",
    }


async def code_understanding(state: MOState) -> MOState:
    task_id = state.get("task_id", "")
    goal = state.get("goal", "")
    ctx = get_context(task_id)

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="分析代码结构与执行路径",
        logs=["code understanding started"],
    )

    vector_store = ctx.vector_store_factory(task_id)
    hits = await vector_store.query(goal or "main entrypoint", n=5)
    context_snippets = "\n\n".join(
        f"[{h['locator']}]\n{h['document'][:800]}" for h in hits
    )

    profile = ctx.model_gateway.select(need_reasoning=True, need_json=True)
    prompt = (
        "Given the research goal and code snippets, respond with JSON:\n"
        '{"core_modules":["..."], "execution_path":"..."}\n\n'
        f"Goal: {goal}\n\nSnippets:\n{context_snippets[:6000]}"
    )
    raw = await ctx.model_gateway.complete(
        profile,
        [{"role": "user", "content": prompt}],
        max_tokens=512,
    )
    parsed = _parse_insights(raw)
    core_modules = parsed.get("core_modules") or []
    if isinstance(core_modules, list) and core_modules and isinstance(core_modules[0], str):
        modules = core_modules
    elif isinstance(core_modules, list) and core_modules:
        modules = re.findall(r'"([^"]+)"', str(core_modules[0]))
    else:
        modules = re.findall(r'"([^"]+)"', raw)[:5]

    execution_path = parsed.get("execution_path") or ""
    if not execution_path:
        match = re.search(r'"execution_path"\s*:\s*"([^"]+)"', raw)
        execution_path = match.group(1) if match else "unknown"

    code_insights = list(state.get("code_insights") or [])
    evidence_ids: list[str] = []

    # 使用已摄取仓库列表（由 repo_ingest 节点填充）作为归因依据
    ingested = (
        state.get("ingested_repos")
        or state.get("repo_urls")
        or ["unknown"]
    )
    primary_repo = ingested[0]

    for module in modules[:10]:
        item = EvidenceItem(
            id=uuid.uuid4().hex,
            task_id=task_id,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri=primary_repo,
            locator=f"{CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX}{module}",
            quote_or_summary=f"{CODE_INSIGHT_PREFIX_CORE_MODULE} {module}",
            strength=EvidenceStrength.MEDIUM,
            created_at=datetime.now(timezone.utc),
        )
        eid = ctx.evidence_service.add(item)
        evidence_ids.append(eid)
        code_insights.append(
            {
                "type": "core_module",
                "module": module,
                "evidence_id": eid,
                "label": ClaimLabel.INFERENCE.value,
            }
        )

    path_item = EvidenceItem(
        id=uuid.uuid4().hex,
        task_id=task_id,
        source_type=SourceType.MODEL_INFERENCE,
        source_uri=primary_repo,
        locator=CODE_INSIGHT_LOCATOR_EXECUTION_PATH,
        quote_or_summary=str(execution_path)[:2000],
        strength=EvidenceStrength.MEDIUM,
        created_at=datetime.now(timezone.utc),
    )
    path_eid = ctx.evidence_service.add(path_item)
    evidence_ids.append(path_eid)
    code_insights.append(
        {
            "type": "execution_path",
            "path": execution_path,
            "evidence_id": path_eid,
            "label": ClaimLabel.INFERENCE.value,
        }
    )

    # 为每个已摄取仓库生成汇总 evidence
    for repo_url in ingested:
        summary_item = EvidenceItem(
            id=uuid.uuid4().hex,
            task_id=task_id,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri=repo_url,
            locator=CODE_INSIGHT_LOCATOR_REPO_SUMMARY,
            quote_or_summary=(
                f"Code understanding for {repo_url}: "
                f"{len(modules)} core modules, execution path: {execution_path}"
            )[:2000],
            strength=EvidenceStrength.MEDIUM,
            created_at=datetime.now(timezone.utc),
        )
        seid = ctx.evidence_service.add(summary_item)
        evidence_ids.append(seid)
        code_insights.append(
            {
                "type": "repo_summary",
                "repo_url": repo_url,
                "evidence_id": seid,
                "label": ClaimLabel.INFERENCE.value,
            }
        )

    # 从 DB 重建 evidence_items（避免 state 累积重复）
    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "code_insights": code_insights,
        "evidence_items": evidence_items,
    }
