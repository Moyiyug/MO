"""沙箱守卫与 sandbox_runner 节点测试（R-004）。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from langgraph.types import Command
from sqlmodel import Session

from mo_api.adapters.paper_research import GPTResearcherAdapter, PaperQAAdapter
from mo_api.adapters.repo_ingest import GitingestAdapter
from mo_api.adapters.sandbox import SandboxGuardError, SandboxRunner
from mo_api.config import Settings
from mo_api.models.enums import (
    EvidenceStrength,
    NodeStatus,
    SourceType,
    STATIC_REPRO_ASSESSMENT_LABEL,
    TaskStatus,
)
from mo_api.models.evidence import EvidenceItem
from mo_api.models.repo import RepoCard
from mo_api.services.evidence_service import EvidenceService
from mo_api.services.event_bus import EventBus
from mo_api.storage.repositories import EvidenceRepository, RepoCardRepository
from mo_api.storage.tables import TaskTable
from mo_api.workflows.execute_context import ExecuteContext, clear_context, register_context
from mo_api.workflows.nodes.sandbox_runner import sandbox_runner
from mo_api.workflows.state import MOState


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        sandbox_enabled=True,
        sandbox_workdir_base=str(tmp_path / "repos"),
        sandbox_command_whitelist="python --version,pytest",
        sandbox_timeout_seconds=5,
    )


def test_guard_rejects_shell_metachar(tmp_path: Path) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")
    with pytest.raises(SandboxGuardError):
        runner.guard("python --version; rm -rf /", cwd)


def test_guard_rejects_non_whitelist(tmp_path: Path) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")
    with pytest.raises(SandboxGuardError):
        runner.guard("curl https://evil.example", cwd)


def test_guard_rejects_outside_workdir(tmp_path: Path) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(SandboxGuardError):
        runner.guard("python --version", outside.resolve())


def test_guard_accepts_whitelist(tmp_path: Path) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")
    runner.guard("python --version", cwd)


@pytest.mark.asyncio
async def test_run_mock_subprocess(tmp_path: Path, monkeypatch) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")

    class _Proc:
        returncode = 0

        async def communicate(self):
            return b"ok", b""

        def kill(self):
            pass

    async def fake_exec(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await runner.run("python --version", cwd)
    assert result.guard_rejected is False
    assert result.exit_code == 0
    assert "ok" in result.stdout_tail


@pytest.mark.asyncio
async def test_run_timeout(tmp_path: Path, monkeypatch) -> None:
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")

    class _Proc:
        returncode = None

        async def communicate(self):
            await asyncio.sleep(10)
            return b"", b""

        def kill(self):
            self.returncode = -9

    async def fake_exec(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = await runner.run("python --version", cwd)
    assert result.timed_out is True


@pytest.mark.asyncio
async def test_sandbox_node_skipped_when_disabled(engine, tmp_path) -> None:
    task_id = "sandbox-skip"
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="test",
                repo_urls=["https://github.com/o/r"],
                status=TaskStatus.EXECUTING.value,
                permissions={"allow_smoke_test": True},
            )
        )
        session.commit()
        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})(),
                vector_store_factory=lambda tid: type("VS", (), {"add_chunks": lambda *a, **k: None})(),
                sandbox_runner=SandboxRunner(
                    Settings(sandbox_enabled=False, sandbox_workdir_base=str(tmp_path))
                ),
            ),
        )
        try:
            state: MOState = {
                "task_id": task_id,
                "permissions": {"allow_smoke_test": True},
                "errors": [],
            }
            result = await sandbox_runner(state)
            assert result == {}
        finally:
            clear_context(task_id)


@pytest.mark.asyncio
async def test_sandbox_node_writes_run_log_on_approval(
    engine, tmp_path, monkeypatch
) -> None:
    task_id = "sandbox-run"
    settings = _settings(tmp_path)
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="test",
                repo_urls=["https://github.com/o/r"],
                status=TaskStatus.EXECUTING.value,
                permissions={"allow_smoke_test": True},
            )
        )
        RepoCardRepository(session).create(
            RepoCard(
                id="card1",
                task_id=task_id,
                repo_url="https://github.com/o/r",
                repo_name="r",
                summary="demo",
                test_commands=["python --version"],
                evidence_ids=[],
            )
        )
        session.commit()

        runner = SandboxRunner(settings)

        class _Proc:
            returncode = 0

            async def communicate(self):
                return b"Python 3.13", b""

            def kill(self):
                pass

        async def fake_exec(*args, **kwargs):
            return _Proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})(),
                vector_store_factory=lambda tid: type("VS", (), {"add_chunks": lambda *a, **k: None})(),
                sandbox_runner=runner,
            ),
        )
        try:
            import mo_api.workflows.nodes.sandbox_runner as mod

            monkeypatch.setattr(mod, "get_settings", lambda: settings)
            monkeypatch.setattr(
                mod,
                "interrupt",
                lambda payload: {"approved": True},
            )
            state: MOState = {
                "task_id": task_id,
                "permissions": {"allow_smoke_test": True},
                "errors": [],
            }
            result = await sandbox_runner(state)
            assert result.get("sandbox_completed") is True
            logs = EvidenceRepository(session).list_by_task(task_id)
            run_logs = [e for e in logs if e.source_type is SourceType.RUN_LOG]
            assert len(run_logs) >= 1
        finally:
            clear_context(task_id)


def test_static_repro_label_unchanged_without_claiming_success() -> None:
    """无 run log 时复现评估仍称 static_reproducibility_assessment（R-003）。"""
    assert STATIC_REPRO_ASSESSMENT_LABEL == "static_reproducibility_assessment"


def test_guard_no_longer_rejects_parentheses(tmp_path: Path) -> None:
    """FIX-1: 括号不再被正则拒绝（仍受白名单保护）。"""
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")
    # 括号本身不再触发 SandboxGuardError（但白名单仍会拒绝非白名单命令）
    try:
        runner.guard("echo (test)", cwd)
    except SandboxGuardError as e:
        assert "not in whitelist" in str(e)  # 白名单拒绝，非正则拒绝


def test_guard_no_longer_rejects_dollar(tmp_path: Path) -> None:
    """FIX-1: $ 不再被正则拒绝。"""
    runner = SandboxRunner(_settings(tmp_path))
    cwd = runner.resolve_workdir("t1", "https://github.com/o/r")
    try:
        runner.guard("echo $HOME", cwd)
    except SandboxGuardError as e:
        assert "not in whitelist" in str(e)


@pytest.mark.asyncio
async def test_rerun_resets_high_risk_permissions(client, created_task_id) -> None:
    """FIX-3: rerun 应重置 allow_web_search/allow_smoke_test。"""
    r = await client.post(f"/api/tasks/{created_task_id}/rerun")
    assert r.status_code == 201
    new_id = r.json()["task_id"]
    detail = await client.get(f"/api/tasks/{new_id}")
    perms = detail.json()["permissions"]
    assert perms["allow_web_search"] is False
    assert perms["allow_smoke_test"] is False
    assert perms["allow_dependency_install"] is False


@pytest.mark.asyncio
async def test_sandbox_node_all_guard_rejected_sets_false(engine, tmp_path, monkeypatch) -> None:
    """FIX-6: 全部命令被 guard 拒绝时 sandbox_completed=False。"""
    from mo_api.models.repo import RepoCard
    from mo_api.storage.repositories import RepoCardRepository

    task_id = "sandbox-guard-fail"
    with Session(engine) as session:
        session.add(
            TaskTable(
                id=task_id,
                goal="test",
                repo_urls=["https://github.com/o/r"],
                status=TaskStatus.EXECUTING.value,
                permissions={"allow_smoke_test": True},
            )
        )
        RepoCardRepository(session).create(
            RepoCard(
                id="card_guard",
                task_id=task_id,
                repo_url="https://github.com/o/r",
                repo_name="r",
                summary="demo",
                test_commands=["curl evil.com"],
                evidence_ids=[],
            )
        )
        session.commit()

        settings = Settings(
            sandbox_enabled=True,
            sandbox_workdir_base=str(tmp_path / "repos"),
            sandbox_command_whitelist="python --version,pytest",
            sandbox_timeout_seconds=5,
        )
        runner = SandboxRunner(settings)
        register_context(
            task_id,
            ExecuteContext(
                task_id=task_id,
                event_bus=EventBus(),
                evidence_service=EvidenceService(session),
                repo_adapter=GitingestAdapter(),
                paper_adapter=PaperQAAdapter(model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})()),
                web_adapter=GPTResearcherAdapter(),
                model_gateway=type("G", (), {"select": lambda s, **k: None, "complete": lambda *a, **k: ""})(),
                vector_store_factory=lambda tid: type("VS", (), {"add_chunks": lambda *a, **k: None})(),
                sandbox_runner=runner,
            ),
        )
        try:
            import mo_api.workflows.nodes.sandbox_runner as mod
            monkeypatch.setattr(mod, "get_settings", lambda: settings)
            monkeypatch.setattr(mod, "interrupt", lambda payload: {"approved": True})
            state: MOState = {
                "task_id": task_id,
                "permissions": {"allow_smoke_test": True},
                "errors": [],
            }
            result = await sandbox_runner(state)
            assert result.get("sandbox_completed") is False
        finally:
            clear_context(task_id)
