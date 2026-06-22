"""ReportService seed + polish integration tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.enums import ClaimLabel, TaskStatus
from mo_api.models.report import REPORT_SECTION_KEYS
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.services.report_service import ReportService
from mo_api.storage.repositories import ReportSectionSeedRepository
from mo_api.storage.tables import TaskTable


def _seed_reportable_task(session: Session, task_id: str) -> None:
    session.add(
        TaskTable(
            id=task_id,
            goal="测试目标",
            repo_urls=["https://github.com/owner/repo-a"],
            paper_urls=[],
            output_language="zh",
            template=None,
            permissions={"allow_repo_clone": True},
            status=TaskStatus.REPORT_DRAFT.value,
        )
    )
    session.commit()


def _fake_gateway() -> MagicMock:
    async def _complete(profile, messages, **kwargs):
        content = messages[0]["content"]
        if "MO 报告章节编辑器" in content:
            return (
                '{"summary":"摘要","reader_markdown":"润色后的正文","warnings":[]}'
            )
        if "MO 最终报告编辑器" in content:
            return (
                "# MO 深度调研报告\n\n"
                "## 结论先行\n\n"
                "基于对候选仓库的深入分析、资料调研和对比矩阵评估，本次研究的核心判断是："
                "候选方案在技术路线、工程成熟度和适用场景上各有侧重，暂无可无脑推荐的单一最优方案。"
                "用户需结合具体场景需求和资源条件做出最终选型判断，本报告仅提供基于当前证据的综合分析。\n\n"
                "## 为什么是这个判断\n\n"
                "此判断基于仓库分析、代码结构解读、PaperQA 资料调研以及多维度对比矩阵的系统评估。"
                "虽然静态评估提供了较为全面的分析基础，但由于缺少实际运行日志，复现相关的结论仅属于静态推断。\n\n"
                "## 候选方案如何理解\n\n"
                "各候选方案在核心抽象、技术栈选择和目标场景方面存在明显差异。"
                "通过仓库档案分析，每个方案都有其独特的设计哲学和适用边界。\n\n"
                "## 关键权衡\n\n"
                "在选择方案时需要重点关注工程成熟度与前沿创新的平衡、"
                "文档完整度与社区活跃度的关系、以及复现难易度与技术复杂度的矛盾。\n\n"
                "## 不确定性与边界\n\n"
                "本次研究存在以下不确定性和边界：复现评估均为静态分析，未经实际运行验证；"
                "部分证据为弱证据或模型推断，需要人工审核确认；对比矩阵的权重设置可能影响排名。\n\n"
                "## 下一步验证路线\n\n"
                "建议对排名靠前的仓库进行实际安装和冒烟测试验证；"
                "补充弱证据相关的文档和代码验证；结合具体业务场景进行概念验证开发。\n"
            )
        if "执行摘要" in content or "execution summary" in content.lower():
            return "执行叙述。"
        if "技术路线" in content or "technical route" in content.lower():
            return "技术叙述。"
        if "研究综合" in content or "research synthesis" in content.lower():
            return (
                '{"thesis":"初步判断测试目标相关的技术方案各有侧重。",'
                '"key_insights":["关键洞察1"],'
                '"repo_interpretations":{"repo-a":"已采集证据"},'
                '"tradeoffs":["权衡1"],'
                '"uncertainty":["不确定性1"],'
                '"next_questions":["下一步验证1"],'
                '"evidence_ids":[]}'
            )
        return "叙述。"

    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    gateway.complete = AsyncMock(side_effect=_complete)
    return gateway


@pytest.mark.asyncio
async def test_report_sections_preserve_structured_markdown_and_seed_metadata(
    engine,
) -> None:
    task_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)
        ReportSectionSeedRepository(session).upsert(
            ReportSectionSeed(
                id=uuid.uuid4().hex,
                task_id=task_id,
                section_key="repo_overview",
                node="repo_ingest",
                title="仓库概览",
                narrative_seed="这是节点阶段生成的仓库概览种子。",
                structured_data={"repo_count": 1},
                evidence_ids=[],
                warnings=[],
                created_at=now,
                updated_at=now,
            )
        )

    with Session(engine) as session:
        report = await ReportService(
            session,
            gateway=_fake_gateway(),
        ).generate_async(task_id)

    assert [section.key for section in report.sections] == REPORT_SECTION_KEYS

    section = next(s for s in report.sections if s.key == "repo_overview")
    assert section.markdown == "润色后的正文"
    assert section.metadata["structured_markdown"]
    # Phase 3: seed_nodes 包含 repo_ingest + research_synthesis
    assert "repo_ingest" in section.metadata["seed_nodes"]
    assert "research_synthesis" in section.metadata["seed_nodes"]
    assert len(section.metadata["seed_narratives"]) >= 2
    assert "这是节点阶段生成的仓库概览种子。" in section.metadata["seed_narratives"]
    # seed_structured_data 包含原始数据 + synthesis 数据
    assert len(section.metadata["seed_structured_data"]) >= 2
    assert section.metadata["polish_status"] == "polished"

    background = next(s for s in report.sections if s.key == "task_background")
    assert len(background.claims) == 1
    assert background.claims[0].label is ClaimLabel.FACT
    assert background.claims[0].evidence_ids == background.evidence_ids
    assert background.markdown == "润色后的正文"


@pytest.mark.asyncio
async def test_report_polish_keeps_order_and_repro_boundary(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_reportable_task(session, task_id)

    with Session(engine) as session:
        report = await ReportService(
            session,
            gateway=_fake_gateway(),
        ).generate_async(task_id)

    assert [section.key for section in report.sections] == REPORT_SECTION_KEYS
    assert len(report.sections) == 13
    for section in report.sections:
        assert "structured_markdown" in section.metadata
        assert section.metadata["polish_status"] == "polished"

    reproducibility = next(
        section for section in report.sections if section.key == "reproducibility"
    )
    assert "复现成功" not in reproducibility.markdown
    assert "复现成功" not in report.markdown
