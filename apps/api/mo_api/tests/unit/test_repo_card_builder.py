"""RepoCard 构建器单元测试（F-003 / F-005）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.agents.repo_card import build_repo_card
from mo_api.models.enums import ClaimLabel, EvidenceStrength, SourceType
from mo_api.models.evidence import EvidenceItem
from mo_api.models.repo import RepoCard, RepoDigest
from mo_api.services.evidence_service import EvidenceService


def _digest(**kw) -> RepoDigest:
    defaults = {
        "summary": "A test repository",
        "tree": "src/main.py\nREADME.md\nLICENSE",
        "content": {
            "README.md": "# Test Repo",
            "LICENSE": "MIT License\nCopyright (c) 2024",
            "requirements.txt": "requests>=2.0\nflask==3.0",
            "src/main.py": "def main(): pass",
            "tests/test_main.py": "def test_main(): pass",
            "docs/index.md": "# Docs",
        },
        "source_uri": "https://github.com/o/r",
    }
    defaults.update(kw)
    return RepoDigest(**defaults)


def _fake_gateway(*, llm_ok: bool = True, llm_result: str | None = None):
    gw = MagicMock()
    gw.select = MagicMock(return_value=MagicMock(id="fake"))
    if llm_ok:
        gw.complete = AsyncMock(
            return_value=llm_result
            or '{"project_type":"library","entrypoints":["main.py"],"risks":["low coverage"]}'
        )
    else:
        gw.complete = AsyncMock(side_effect=Exception("LLM error"))
    return gw


@pytest.mark.asyncio
async def test_deterministic_fields_have_fact_evidence(engine) -> None:
    """确定性字段（license/deps/docs/test/language）应有 FACT 标签 + EvidenceItem。"""
    task_id = "rc-det"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)

    assert card.field_labels.get("license") == ClaimLabel.FACT.value
    assert card.field_labels.get("dependencies") == ClaimLabel.FACT.value
    assert card.field_labels.get("docs_paths") == ClaimLabel.FACT.value
    assert card.field_labels.get("test_commands") == ClaimLabel.FACT.value
    assert card.field_labels.get("primary_language") == ClaimLabel.FACT.value
    # 确定性字段应有证据 ID
    assert len(card.evidence_ids) >= 4  # license + deps + docs + tests + language


@pytest.mark.asyncio
async def test_docs_paths_generate_evidence(engine) -> None:
    """docs_paths 中每个路径应生成独立的 EvidenceItem。"""
    task_id = "rc-docs"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)
        items = svc.list_by_task(task_id)

    doc_evidence = [
        i for i in items
        if i.locator and i.locator.startswith("docs/")
    ]
    assert len(doc_evidence) >= 1
    assert all(i.source_type == SourceType.REPO_FILE for i in doc_evidence)
    assert all(i.strength == EvidenceStrength.STRONG for i in doc_evidence)


@pytest.mark.asyncio
async def test_test_paths_generate_evidence(engine) -> None:
    """test_paths 中每个路径应生成独立的 EvidenceItem。"""
    task_id = "rc-test"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)
        items = svc.list_by_task(task_id)

    test_evidence = [
        i for i in items
        if i.locator and "test" in i.locator.lower()
    ]
    assert len(test_evidence) >= 1
    assert all(i.source_type == SourceType.REPO_FILE for i in test_evidence)


@pytest.mark.asyncio
async def test_llm_fields_are_inference(engine) -> None:
    """LLM 推断字段（project_type/entrypoints/risks）应标 INFERENCE。"""
    task_id = "rc-inf"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)

    assert card.field_labels.get("project_type") == ClaimLabel.INFERENCE.value
    assert card.field_labels.get("entrypoints") == ClaimLabel.INFERENCE.value
    assert card.field_labels.get("risks") == ClaimLabel.INFERENCE.value
    assert card.project_type == "library"
    assert "main.py" in card.entrypoints
    assert len(card.risks) >= 1


@pytest.mark.asyncio
async def test_llm_failure_marks_pending(engine) -> None:
    """LLM 调用失败时推断字段应标 PENDING——绝不静默标 fact。"""
    task_id = "rc-pend"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(
            task_id, digest, _fake_gateway(llm_ok=False), svc,
        )

    assert card.field_labels.get("project_type") == ClaimLabel.PENDING.value
    assert card.field_labels.get("entrypoints") == ClaimLabel.INFERENCE.value
    assert card.field_labels.get("risks") == ClaimLabel.PENDING.value
    assert card.project_type is None
    assert card.entrypoints
    assert card.risks == []


@pytest.mark.asyncio
async def test_dependency_parsing_merges_multiple_sources(engine) -> None:
    """应解析 requirements.txt + pyproject.toml + package.json 并去重合并。"""
    task_id = "rc-deps"
    digest = _digest(
        content={
            "requirements.txt": "requests>=2.0\nflask==3.0",
            "pyproject.toml": '[project]\ndependencies = ["numpy", "pandas"]',
            "LICENSE": "MIT",
        },
    )
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)

    deps = card.dependencies
    assert "requests>=2.0" in deps
    assert "flask==3.0" in deps
    assert "numpy" in deps
    assert "pandas" in deps


@pytest.mark.asyncio
async def test_primary_language_detection(engine) -> None:
    """根据文件扩展名检测主语言。"""
    task_id = "rc-lang"
    digest = _digest(
        content={
            "main.py": "x",
            "lib.py": "x",
            "utils.js": "x",
            "README.md": "x",
            "LICENSE": "MIT",
        },
    )
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)

    assert card.primary_language == "Python"
    # 验证有 primary_language 的 evidence
    items = svc.list_by_task(task_id)
    lang_items = [
        i for i in items
        if i.locator == "<file-tree>" and "Primary language" in i.quote_or_summary
    ]
    assert len(lang_items) == 1


@pytest.mark.asyncio
async def test_raw_python_rag_digest_infers_language_and_type(engine) -> None:
    task_id = "rc-raw-rag"
    digest = _digest(
        summary="Raw GitHub fallback ingest",
        tree="README.md\npyproject.toml",
        content={
            "README.md": (
                "# LlamaIndex\n"
                "A data framework for LLM applications and retrieval workflows."
            ),
            "pyproject.toml": (
                "[project]\n"
                "dependencies = [\"llama-index-core>=0.14\", \"nltk>=3\"]"
            ),
            "LICENSE": "The MIT License",
        },
        source_uri="https://github.com/run-llama/llama_index",
    )

    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(llm_ok=False), svc)

    assert card.primary_language == "Python"
    assert card.field_labels.get("primary_language") == ClaimLabel.INFERENCE.value
    assert card.project_type == "LLM/RAG application framework"
    assert card.field_labels.get("project_type") == ClaimLabel.INFERENCE.value


@pytest.mark.asyncio
async def test_repo_card_has_evidence_ids(engine) -> None:
    """RepoCard 的 evidence_ids 应对应实际创建的 EvidenceItem 数量。"""
    task_id = "rc-eids"
    digest = _digest()
    with Session(engine) as session:
        svc = EvidenceService(session)
        card = await build_repo_card(task_id, digest, _fake_gateway(), svc)
        items = svc.list_by_task(task_id)

    # 所有 evidence_ids 应存在于 DB
    db_ids = {i.id for i in items}
    for eid in card.evidence_ids:
        assert eid in db_ids, f"evidence {eid} not found in DB"
    # 至少 license + deps + docs + tests + language
    assert len(card.evidence_ids) >= 4
