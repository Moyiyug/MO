"""sandbox_runner 节点：审批后于沙箱执行白名单 smoke test（R-004）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langgraph.types import interrupt
from sqlmodel import Session

from ...adapters.sandbox import SandboxRunner
from ...config import get_settings
from ...models.enums import EvidenceStrength, NodeStatus, SourceType
from ...models.evidence import EvidenceItem
from ...storage import db
from ...storage.repositories import RepoCardRepository
from ..execute_context import get_context, maybe_skip_node, publish_node_event
from ..state import MOState

NODE_ID = "sandbox_runner"


async def sandbox_runner(state: MOState) -> MOState:
    settings = get_settings()
    task_id = state.get("task_id", "")
    ctx = get_context(task_id)
    permissions = state.get("permissions") or {}

    if await maybe_skip_node(state, NODE_ID, ctx):
        return {}

    if not settings.sandbox_enabled or not permissions.get("allow_smoke_test"):
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.SKIPPED,
            input_summary="沙箱未启用或未授权冒烟测试",
            logs=["sandbox_runner skipped: disabled or allow_smoke_test=false"],
        )
        return {}

    existing_run_logs = [
        item
        for item in ctx.evidence_service.list_by_task(task_id)
        if item.source_type is SourceType.RUN_LOG
    ]
    if existing_run_logs:
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.SKIPPED,
            input_summary="已有 run_log 证据，幂等跳过",
            evidence_ids=[e.id for e in existing_run_logs],
            logs=["sandbox_runner skipped: run_log already exists"],
        )
        return {}

    with Session(db.get_engine()) as session:
        repo_cards = RepoCardRepository(session).list_by_task(task_id)

    if not repo_cards:
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.SKIPPED,
            input_summary="无仓库可执行 smoke test",
            logs=["sandbox_runner skipped: no repo cards"],
        )
        return {}

    commands_preview: list[str] = []
    for card in repo_cards:
        cmds = card.test_commands or ["python --version"]
        commands_preview.extend(f"{SandboxRunner.repo_slug(card.repo_url)}: {c}" for c in cmds)

    decision = interrupt(
        {
            "action": "smoke_test",
            "requires_approval": True,
            "node": NODE_ID,
            "commands": commands_preview,
        }
    )
    if not decision.get("approved"):
        await publish_node_event(
            ctx,
            NODE_ID,
            NodeStatus.FAILED,
            error_message="冒烟测试未获批准",
            logs=["sandbox_runner rejected by user"],
        )
        errors = list(state.get("errors") or [])
        errors.append({"node": NODE_ID, "msg": "smoke test not approved"})
        return {"errors": errors}

    await publish_node_event(
        ctx,
        NODE_ID,
        NodeStatus.RUNNING,
        input_summary="沙箱 smoke test 执行中",
        logs=["sandbox_runner started"],
    )

    runner = ctx.sandbox_runner
    evidence_ids: list[str] = []
    run_logs: list[str] = []
    any_executed = False

    for card in repo_cards:
        workdir = runner.resolve_workdir(task_id, card.repo_url)
        for cmd in card.test_commands or ["python --version"]:
            result = await runner.run(cmd, workdir)
            if not result.guard_rejected:
                any_executed = True
            summary_parts = [
                f"cmd={result.command}",
                f"exit={result.exit_code}",
                f"timed_out={result.timed_out}",
            ]
            if result.guard_rejected:
                summary_parts.append(f"guard={result.guard_reason}")
            if result.stdout_tail:
                summary_parts.append(f"stdout_tail={result.stdout_tail[:500]}")
            if result.stderr_tail:
                summary_parts.append(f"stderr_tail={result.stderr_tail[:500]}")

            quote = "; ".join(summary_parts)
            run_logs.append(quote)

            item = EvidenceItem(
                id=uuid.uuid4().hex,
                task_id=task_id,
                source_type=SourceType.RUN_LOG,
                source_uri=card.repo_url,
                locator=f"sandbox:{cmd}",
                quote_or_summary=quote[:4000],
                strength=(
                    EvidenceStrength.STRONG
                    if result.exit_code == 0 and not result.timed_out
                    else EvidenceStrength.WEAK
                ),
                created_at=datetime.now(timezone.utc),
            )
            eid = ctx.evidence_service.add(item)
            evidence_ids.append(eid)

    # 更新 reproducibility 报告：有 run_log 则标记为实测
    if any_executed:
        with Session(db.get_engine()) as session:
            from ...storage.repositories import ReproducibilityRepository
            repro_repo = ReproducibilityRepository(session)
            existing = repro_repo.get_by_task(task_id)
            if existing is not None:
                for score in existing.scores:
                    score.assessment_label = "smoke_test_executed"
                repro_repo.upsert_by_task(existing)

    evidence_items = [
        item.model_dump(mode="json")
        for item in ctx.evidence_service.list_by_task(task_id)
    ]

    return {
        "evidence_items": evidence_items,
        "sandbox_completed": any_executed,
        "evidence_ids": evidence_ids,
    }
