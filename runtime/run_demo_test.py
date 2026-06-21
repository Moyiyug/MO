"""Run the real RAG demo flow through the local MO backend.

The script exercises the product API, not internal workflow shortcuts:
create task -> PlanMode -> clarify -> select first three candidates -> approve
-> ExecuteMode -> report generation/export -> quality gate.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any

import httpx


BASE_URL = "http://localhost:8000"
DB_PATH = Path("runtime/mo.db")
EXPORT_PATH = Path("runtime/test_final.md")
GOAL = "RAG 架构调研：对比 LangChain、LlamaIndex、Haystack 的工程成熟度、RAG 管道设计与静态可复现性"


async def require_ok(resp: httpx.Response, label: str) -> httpx.Response:
    if resp.status_code >= 400:
        print(f"{label} failed: {resp.status_code} {resp.text[:500]}", flush=True)
        resp.raise_for_status()
    return resp


def waiting_nodes(task_id: str) -> list[str]:
    if not DB_PATH.exists():
        return []
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            """
            select payload
            from node_events
            where task_id = ? and status = 'waiting_user'
            order by seq
            """,
            (task_id,),
        ).fetchall()
    finally:
        con.close()
    nodes: list[str] = []
    for (payload,) in rows:
        if not payload:
            continue
        import json

        data = json.loads(payload)
        node = data.get("node")
        if isinstance(node, str) and node not in nodes:
            nodes.append(node)
    return nodes


def failed_events(task_id: str) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            """
            select payload
            from node_events
            where task_id = ? and status = 'failed'
            order by seq
            """,
            (task_id,),
        ).fetchall()
    finally:
        con.close()
    events: list[dict[str, Any]] = []
    for (payload,) in rows:
        if not payload:
            continue
        import json

        events.append(json.loads(payload))
    return events


def clarification_answers(plan: dict[str, Any]) -> list[dict[str, str]]:
    answers: list[dict[str, str]] = []
    for question in plan.get("clarifying_questions") or []:
        if not question.get("required") or question.get("answer"):
            continue
        qid = question.get("id")
        if not qid:
            continue
        answer = "综合对比，重点关注工程成熟度、RAG 管道设计、文档完整度和静态可复现性。"
        if qid == "comparison_focus":
            answer = "综合对比"
        answers.append({"question_id": str(qid), "answer": answer})
    return answers


def validate_quality(
    *,
    repos: list[dict[str, Any]],
    comparison: dict[str, Any],
    report: dict[str, Any],
    markdown: str,
) -> list[str]:
    problems: list[str] = []
    repo_names = {str(r.get("repo_name", "")).lower() for r in repos}
    if len(repos) < 3:
        problems.append(f"expected at least 3 repos, got {len(repos)}")
    if not any("llama" in name for name in repo_names):
        problems.append("llama_index was not ingested")

    rankings = comparison.get("rankings") or []
    scores = comparison.get("scores") or []
    if len(rankings) < 3:
        problems.append(f"expected at least 3 rankings, got {len(rankings)}")
    unique_scores = {round(float(s.get("score", 0)), 3) for s in scores}
    if len(unique_scores) <= 1:
        problems.append("comparison scores are still uniform")
    weak_rationales = [
        s for s in scores if "评分依据不足" in str(s.get("rationale", ""))
    ]
    if len(weak_rationales) == len(scores) and scores:
        problems.append("all comparison rationales are weak fallback text")

    sections = report.get("sections") or []
    if len(sections) != 13:
        problems.append(f"expected 13 report sections, got {len(sections)}")
    for required in ("comparison_matrix", "recommendation", "reproducibility"):
        if not any(s.get("key") == required for s in sections):
            problems.append(f"missing report section: {required}")

    forbidden = ("复现成功", "实际运行成功", "实测通过", "运行后完成", "已实际运行")
    for line in markdown.splitlines():
        if any(guard in line for guard in ("不代表", "不得", "不可", "不能", "未进行")):
            continue
        for phrase in forbidden:
            if phrase in line:
                problems.append(f"report contains forbidden no-run-log phrase: {phrase}")
    if "static_reproducibility_assessment" not in markdown and "静态复现" not in markdown:
        problems.append("report does not clearly mark static reproducibility")
    return problems


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=900) as client:
        print("0. Waiting for backend health...", flush=True)
        for _ in range(30):
            try:
                health = await client.get("/health", timeout=5)
                if health.status_code == 200:
                    break
            except Exception:
                await asyncio.sleep(1)
        else:
            raise RuntimeError("backend health check failed")

        print("1. Creating RAG task...", flush=True)
        created = await require_ok(
            await client.post(
                "/api/tasks",
                json={
                    "goal": GOAL,
                    "repo_urls": [],
                    "template": "rag_framework_comparison",
                    "output_language": "zh",
                    "permissions": {
                        "allow_web_search": True,
                        "allow_repo_clone": True,
                        "allow_smoke_test": False,
                        "allow_dependency_install": False,
                    },
                },
            ),
            "create task",
        )
        task_id = created.json()["task_id"]
        print(f"   task_id={task_id}", flush=True)

        print("2. Generating plan...", flush=True)
        plan = (
            await require_ok(await client.post(f"/api/tasks/{task_id}/plan"), "plan")
        ).json()
        candidates = plan.get("repo_candidates") or []
        if len(candidates) < 3:
            raise RuntimeError(f"expected at least 3 candidates, got {len(candidates)}")
        top3 = [c["repo_url"] for c in candidates[:3]]
        for i, cand in enumerate(candidates[:3], 1):
            print(f"   {i}. {cand['repo_name']} -> {cand['repo_url']}", flush=True)

        print("3. Selecting first three candidates...", flush=True)
        await require_ok(
            await client.post(
                f"/api/tasks/{task_id}/repo-candidates",
                json={"selected_repo_urls": top3},
            ),
            "select repo candidates",
        )

        answers = clarification_answers(plan)
        if answers:
            print(f"4. Submitting {len(answers)} clarification answer(s)...", flush=True)
            plan = (
                await require_ok(
                    await client.post(
                        f"/api/tasks/{task_id}/clarifications",
                        json={"answers": answers},
                    ),
                    "clarifications",
                )
            ).json()
        else:
            print("4. No required clarifications.", flush=True)

        print("5. Approving plan...", flush=True)
        approved = await require_ok(
            await client.post(f"/api/tasks/{task_id}/approve-plan", json={}),
            "approve plan",
        )
        print(f"   status={approved.json().get('status')}", flush=True)

        print("6. Executing workflow...", flush=True)
        await require_ok(await client.post(f"/api/tasks/{task_id}/execute"), "execute")

        terminal = {"REPORT_DRAFT", "REVIEW_REQUIRED", "DONE", "FAILED"}
        status = "EXECUTING"
        approved_nodes: set[str] = set()
        for tick in range(360):
            await asyncio.sleep(5)

            for node in waiting_nodes(task_id):
                if node in approved_nodes:
                    continue
                print(f"   approving waiting node: {node}", flush=True)
                await require_ok(
                    await client.post(
                        f"/api/tasks/{task_id}/steps/{node}/approve",
                        json={"approved": True},
                    ),
                    f"approve {node}",
                )
                approved_nodes.add(node)

            task = (
                await require_ok(await client.get(f"/api/tasks/{task_id}"), "task")
            ).json()
            status = task["status"]
            if tick % 6 == 0:
                repos = (
                    await require_ok(
                        await client.get(f"/api/tasks/{task_id}/repos"),
                        "repos",
                    )
                ).json()
                print(f"   [{tick * 5:>4}s] status={status} repos={len(repos)}", flush=True)
            if status in terminal:
                break

        print(f"   terminal status={status}", flush=True)
        if status == "FAILED":
            for event in failed_events(task_id):
                print(
                    f"   FAIL {event.get('node')}: {str(event.get('error_message'))[:300]}",
                    flush=True,
                )
            raise RuntimeError("workflow failed")
        if status not in terminal:
            raise RuntimeError(f"workflow did not finish, last status={status}")

        print("7. Reading repos and comparison...", flush=True)
        repos = (
            await require_ok(await client.get(f"/api/tasks/{task_id}/repos"), "repos")
        ).json()
        comparison_resp = await client.get(f"/api/tasks/{task_id}/comparison")
        await require_ok(comparison_resp, "comparison")
        comparison = comparison_resp.json()
        for repo in repos:
            print(
                f"   repo={repo.get('repo_name')} lang={repo.get('primary_language')} "
                f"type={repo.get('project_type')}",
                flush=True,
            )
        print("   rankings:", flush=True)
        for rank in comparison.get("rankings", []):
            print(
                f"   - {rank['repo_name']}: {float(rank['weighted_total']):.3f}",
                flush=True,
            )

        print("8. Generating/exporting report...", flush=True)
        report = (
            await require_ok(
                await client.post(f"/api/tasks/{task_id}/generate-report", timeout=900),
                "generate report",
            )
        ).json()
        exported = await require_ok(
            await client.post(f"/api/tasks/{task_id}/export"),
            "export",
        )
        EXPORT_PATH.write_text(exported.text, encoding="utf-8")
        print(
            f"   exported {len(exported.text)} chars -> {EXPORT_PATH.as_posix()}",
            flush=True,
        )

        print("9. Quality gate...", flush=True)
        problems = validate_quality(
            repos=repos,
            comparison=comparison,
            report=report,
            markdown=exported.text,
        )
        if problems:
            print("QUALITY FAILED:", flush=True)
            for problem in problems:
                print(f"   - {problem}", flush=True)
            print(f"TASK_ID={task_id}", flush=True)
            raise RuntimeError("demo quality gate failed")

        print("QUALITY OK", flush=True)
        print(f"TASK_ID={task_id}", flush=True)
        print(f"REPORT={EXPORT_PATH.as_posix()}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
