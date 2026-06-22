"""ResearchSynthesisService 单元测试（PRD F4 / F8）。

覆盖：
- parse_json_object 容忍 markdown fence
- extract_seed_field / extract_single_seed_field
- format_digest_for_prompt
- build_research_synthesis_prompt
- evaluate_quality 各质量等级
- synthesize 成功与 fallback
- enforce_boundaries（无 run_log 时补充 uncertainty）
- fallback_synthesis 包含仓库信息
- write_synthesis_seeds 写入 6 个目标 section
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import Session

from mo_api.models.comparison import ComparisonMatrix
from mo_api.models.enums import (
    ClaimLabel,
    EvidenceStrength,
    OutputLanguage,
    SourceType,
    TaskStatus,
)
from mo_api.models.evidence import EvidenceItem
from mo_api.models.plan import Plan
from mo_api.models.repo import RepoCard
from mo_api.models.report_seed import ReportSectionSeed
from mo_api.models.reproducibility import ReproducibilityReport
from mo_api.models.research_synthesis import (
    PaperQAAnswerRecord,
    ResearchQuality,
    ResearchSynthesis,
)
from mo_api.models.task import TaskPermissions, TaskResponse
from mo_api.services.report_context import ReportContext
from mo_api.services.report_evidence import build_evidence_digest
from mo_api.services.report_seed_service import ReportSeedService
from mo_api.services.research_synthesis import (
    ResearchSynthesisService,
    build_research_synthesis_prompt,
    extract_seed_field,
    extract_single_seed_field,
    format_digest_for_prompt,
    parse_json_object,
    write_synthesis_seeds,
)
from mo_api.storage.repositories import ReportSectionSeedRepository
from mo_api.storage.tables import TaskTable


# ── helpers ────────────────────────────────────────────────────────────────


def _make_task(task_id: str, goal: str = "对比 RAG 框架") -> TaskResponse:
    return TaskResponse(
        task_id=task_id,
        goal=goal,
        status=TaskStatus.REPORT_DRAFT,
        repo_urls=["https://github.com/owner/repo-a"],
        paper_urls=[],
        output_language=OutputLanguage.ZH,
        permissions=TaskPermissions(),
        created_at=datetime.now(timezone.utc),
    )


def _make_evidence_item(
    eid: str,
    task_id: str,
    *,
    source_type: SourceType = SourceType.REPO_FILE,
    strength: EvidenceStrength = EvidenceStrength.STRONG,
    quote: str = "test evidence",
) -> EvidenceItem:
    return EvidenceItem(
        id=eid,
        task_id=task_id,
        source_type=source_type,
        source_uri="https://github.com/owner/repo-a",
        locator="README.md",
        quote_or_summary=quote,
        strength=strength,
        created_at=datetime.now(timezone.utc),
    )


def _make_repo_card(task_id: str, name: str = "owner/repo-a") -> RepoCard:
    return RepoCard(
        id=uuid.uuid4().hex,
        task_id=task_id,
        repo_url=f"https://github.com/{name}",
        repo_name=name,
        summary=f"{name} summary",
        evidence_ids=["e1"],
    )


def _make_report_seed(
    task_id: str,
    section_key: str,
    *,
    structured_data: dict | None = None,
    node: str = "paper_research",
) -> ReportSectionSeed:
    now = datetime.now(timezone.utc)
    return ReportSectionSeed(
        id=uuid.uuid4().hex,
        task_id=task_id,
        section_key=section_key,
        node=node,
        title=section_key,
        narrative_seed="seed narrative",
        structured_data=structured_data or {},
        evidence_ids=[],
        warnings=[],
        created_at=now,
        updated_at=now,
    )


def _make_report_context(
    task_id: str,
    *,
    evidence_items: list[EvidenceItem] | None = None,
    repo_cards: list[RepoCard] | None = None,
    report_seeds: list[ReportSectionSeed] | None = None,
    comparison: ComparisonMatrix | None = None,
    reproducibility: ReproducibilityReport | None = None,
) -> ReportContext:
    return ReportContext(
        task=_make_task(task_id),
        plan=MagicMock(spec=Plan),
        events=[],
        repo_cards=repo_cards or [_make_repo_card(task_id)],
        evidence_items=evidence_items or [_make_evidence_item("e1", task_id)],
        comparison=comparison,
        reproducibility=reproducibility,
        report_seeds=report_seeds or [],
    )


def _make_fake_gateway(
    response: str | Exception = '{"thesis":"核心论点","key_insights":["洞察1"],'
    '"repo_interpretations":{"repo-a":"解读"},"tradeoffs":["权衡1"],'
    '"uncertainty":["不确定性1"],"next_questions":["下一步1"],'
    '"evidence_ids":["e1"]}',
) -> MagicMock:
    gateway = MagicMock()
    gateway.select.return_value = MagicMock()
    if isinstance(response, Exception):
        gateway.complete = AsyncMock(side_effect=response)
    else:
        gateway.complete = AsyncMock(return_value=response)
    return gateway


def _seed_task_row(session: Session, task_id: str) -> None:
    session.add(
        TaskTable(
            id=task_id,
            goal="对比 RAG 框架",
            repo_urls=["https://github.com/owner/repo-a"],
            paper_urls=[],
            output_language="zh",
            template=None,
            permissions={"allow_repo_clone": True},
            status=TaskStatus.REPORT_DRAFT.value,
        )
    )
    session.commit()


# ── parse_json_object ─────────────────────────────────────────────────────


def test_parse_json_object_accepts_plain_json() -> None:
    data = parse_json_object('{"thesis":"test","key_insights":[]}')
    assert data["thesis"] == "test"


def test_parse_json_object_accepts_fenced_json() -> None:
    data = parse_json_object('```json\n{"thesis":"test"}\n```')
    assert data["thesis"] == "test"


def test_parse_json_object_accepts_fenced_no_lang() -> None:
    data = parse_json_object('```\n{"key":"val"}\n```')
    assert data["key"] == "val"


def test_parse_json_object_returns_empty_dict_on_invalid() -> None:
    data = parse_json_object("not json at all")
    assert data == {}


def test_parse_json_object_returns_empty_dict_on_non_object() -> None:
    data = parse_json_object("[1, 2, 3]")
    assert data == {}


# ── extract_seed_field ────────────────────────────────────────────────────


def test_extract_seed_field_from_list() -> None:
    seed = _make_report_seed(
        "t1", "paper_supplement",
        structured_data={"paperqa_answers": [
            {"question": "Q1", "answer": "A1", "failed": False}
        ]},
    )
    results = extract_seed_field([seed], "paperqa_answers")
    assert len(results) == 1
    assert results[0]["answer"] == "A1"


def test_extract_seed_field_returns_empty_when_missing() -> None:
    seed = _make_report_seed("t1", "paper_supplement")
    results = extract_seed_field([seed], "nonexistent")
    assert results == []


def test_extract_single_seed_field_returns_string() -> None:
    seed = _make_report_seed(
        "t1", "paper_supplement",
        structured_data={"web_report": "web content here"},
    )
    val = extract_single_seed_field([seed], "web_report")
    assert val == "web content here"


def test_extract_single_seed_field_returns_none_when_missing() -> None:
    seed = _make_report_seed("t1", "paper_supplement")
    val = extract_single_seed_field([seed], "nonexistent")
    assert val is None


# ── format_digest_for_prompt ──────────────────────────────────────────────


def test_format_digest_for_prompt() -> None:
    task_id = uuid.uuid4().hex
    items = [
        _make_evidence_item("e1", task_id, source_type=SourceType.REPO_FILE, strength=EvidenceStrength.STRONG),
        _make_evidence_item("e2", task_id, source_type=SourceType.PAPER, strength=EvidenceStrength.WEAK, quote="weak paper"),
    ]
    digest = build_evidence_digest(items)
    text = format_digest_for_prompt(digest)
    assert "2 条证据" in text
    assert "1 条 weak/missing" in text
    assert "E01" in text


# ── evaluate_quality ──────────────────────────────────────────────────────


def test_evaluate_quality_shallow_when_minimal_context() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    assert quality.research_depth == "shallow"
    assert quality.confidence_level == "low"
    assert quality.repo_card_count == 1
    assert quality.has_paperqa_answer is False
    assert quality.has_web_report is False


def test_evaluate_quality_medium_with_paperqa() -> None:
    task_id = uuid.uuid4().hex
    seed = _make_report_seed(
        task_id, "paper_supplement",
        structured_data={"paperqa_answers": [
            {"question": "Q1", "answer": "A1", "failed": False}
        ]},
    )
    context = _make_report_context(
        task_id,
        repo_cards=[_make_repo_card(task_id, "r1"), _make_repo_card(task_id, "r2")],
        report_seeds=[seed],
    )
    digest = build_evidence_digest(context.evidence_items)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    # paperqa + >=2 repos = 2 points → medium
    assert quality.research_depth == "medium"
    assert quality.has_paperqa_answer is True
    assert quality.repo_card_count == 2


def test_evaluate_quality_deep_with_full_context() -> None:
    task_id = uuid.uuid4().hex
    seeds = [
        _make_report_seed(
            task_id, "paper_supplement",
            structured_data={
                "paperqa_answers": [
                    {"question": "Q1", "answer": "A1", "failed": False}
                ],
                "web_report": "web report content",
            },
        ),
    ]
    # 构造含 run_log 的 evidence 来避免 limitations
    evidence = [
        _make_evidence_item("e1", task_id, source_type=SourceType.REPO_FILE, strength=EvidenceStrength.STRONG),
        _make_evidence_item("e2", task_id, source_type=SourceType.RUN_LOG, strength=EvidenceStrength.STRONG, quote="smoke test passed"),
    ]

    from mo_api.models.comparison import ComparisonMatrix as CM
    comparison = MagicMock(spec=CM)
    reproducibility = MagicMock(spec=ReproducibilityReport)

    context = _make_report_context(
        task_id,
        evidence_items=evidence,
        repo_cards=[
            _make_repo_card(task_id, "r1"),
            _make_repo_card(task_id, "r2"),
        ],
        report_seeds=seeds,
        comparison=comparison,
        reproducibility=reproducibility,
    )
    digest = build_evidence_digest(evidence)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    # paperqa + web_report + >=2 repos + comparison + reproducibility + coverage>=0.7
    # = 6 points → deep/high
    assert quality.research_depth == "deep"
    assert quality.confidence_level == "high"
    assert quality.has_paperqa_answer is True
    assert quality.has_web_report is True
    assert quality.has_comparison is True
    assert quality.has_reproducibility is True


def test_evaluate_quality_notes_weak_evidence() -> None:
    task_id = uuid.uuid4().hex
    evidence = [
        _make_evidence_item("e1", task_id, strength=EvidenceStrength.WEAK, quote="weak"),
        _make_evidence_item("e2", task_id, strength=EvidenceStrength.MISSING, quote="missing"),
    ]
    context = _make_report_context(task_id, evidence_items=evidence)
    digest = build_evidence_digest(evidence)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    assert quality.weak_or_missing_evidence_count == 2
    assert quality.evidence_coverage == 0.0
    assert any("2 条" in lim for lim in quality.limitations)


def test_evaluate_quality_without_paperqa_adds_limitation() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    assert any("PaperQA" in lim for lim in quality.limitations)


def test_evaluate_quality_without_web_report_adds_limitation() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    assert any("联网调研" in lim for lim in quality.limitations)


def test_evaluate_quality_without_run_log_adds_limitation() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    quality = service.evaluate_quality(context, evidence_digest=digest)

    assert any("run_log" in lim for lim in quality.limitations)


# ── enforce_boundaries ────────────────────────────────────────────────────


def test_enforce_boundaries_removes_unknown_evidence_ids() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    synthesis = ResearchSynthesis(
        thesis="test",
        evidence_ids=["e1", "unknown_id"],
    )
    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    result = service._enforce_boundaries(synthesis, context, digest)

    assert "unknown_id" not in result.evidence_ids
    assert "e1" in result.evidence_ids


def test_enforce_boundaries_adds_uncertainty_without_run_log() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)

    synthesis = ResearchSynthesis(thesis="test", uncertainty=[])
    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    result = service._enforce_boundaries(synthesis, context, digest)

    assert any("静态评估" in u for u in result.uncertainty)


def test_enforce_boundaries_adds_weak_evidence_warning() -> None:
    task_id = uuid.uuid4().hex
    evidence = [
        _make_evidence_item("e1", task_id, strength=EvidenceStrength.WEAK, quote="weak"),
    ]
    context = _make_report_context(task_id, evidence_items=evidence)
    digest = build_evidence_digest(evidence)

    synthesis = ResearchSynthesis(thesis="test", uncertainty=[])
    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)
    result = service._enforce_boundaries(synthesis, context, digest)

    assert any("弱" in u or "缺失" in u or "不足" in u for u in result.uncertainty)


# ── synthesize ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_synthesize_returns_valid_synthesis() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)
    gateway = _make_fake_gateway()

    service = ResearchSynthesisService(gateway)
    synthesis, quality, warnings = await service.synthesize(
        context,
        evidence_digest=digest,
    )

    assert synthesis.thesis == "核心论点"
    assert len(synthesis.key_insights) == 1
    assert "repo-a" in synthesis.repo_interpretations
    assert len(synthesis.tradeoffs) == 1
    assert len(synthesis.uncertainty) >= 1
    assert len(synthesis.next_questions) == 1
    assert quality.research_depth in ("shallow", "medium", "deep")
    assert warnings == []


@pytest.mark.asyncio
async def test_synthesize_fallback_does_not_block() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)
    gateway = _make_fake_gateway(RuntimeError("model unavailable"))

    service = ResearchSynthesisService(gateway)
    synthesis, quality, warnings = await service.synthesize(
        context,
        evidence_digest=digest,
    )

    # fallback 仍返回有效 synthesis
    assert synthesis.thesis
    assert synthesis.uncertainty
    assert quality.confidence_level in ("low", "medium", "high")
    assert warnings
    assert any("降级" in w or "fallback" in w.lower() or "失败" in w for w in warnings)


@pytest.mark.asyncio
async def test_synthesize_fallback_on_invalid_json() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)
    # thesis 期望 str 但收到 int → Pydantic ValidationError → fallback
    gateway = _make_fake_gateway('{"thesis": 123, "key_insights": "not_a_list"}')

    service = ResearchSynthesisService(gateway)
    synthesis, quality, warnings = await service.synthesize(
        context,
        evidence_digest=digest,
    )

    # 校验失败触发 fallback
    assert synthesis.thesis
    assert warnings
    assert any("降级" in w or "失败" in w for w in warnings)
    assert quality is not None


# ── fallback_synthesis ────────────────────────────────────────────────────


def test_fallback_synthesis_contains_repo_and_goal() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(
        task_id,
        repo_cards=[
            _make_repo_card(task_id, "owner/r1"),
            _make_repo_card(task_id, "owner/r2"),
        ],
    )
    quality = ResearchQuality(research_depth="shallow", confidence_level="low")
    gateway = _make_fake_gateway()
    service = ResearchSynthesisService(gateway)

    fallback = service._fallback_synthesis(context, quality)

    assert "对比 RAG 框架" in fallback.thesis or "RAG" in fallback.thesis
    assert any("r1" in ri or "r2" in ri for ri in fallback.repo_interpretations)
    assert len(fallback.key_insights) >= 1
    assert len(fallback.uncertainty) >= 1
    assert any("fallback" in u for u in fallback.uncertainty)
    assert len(fallback.next_questions) >= 1


# ── write_synthesis_seeds ─────────────────────────────────────────────────


def test_write_synthesis_seeds_writes_six_sections(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task_row(session, task_id)

    synthesis = ResearchSynthesis(
        thesis="核心论点内容",
        key_insights=["洞察1", "洞察2"],
        repo_interpretations={"owner/repo-a": "解读内容"},
        tradeoffs=["权衡1"],
        uncertainty=["不确定性1"],
        next_questions=["下一步1", "下一步2"],
        evidence_ids=["e1"],
    )
    quality = ResearchQuality(
        research_depth="medium",
        confidence_level="medium",
        evidence_coverage=0.75,
        limitations=["测试限制"],
        has_paperqa_answer=True,
        has_web_report=False,
        repo_card_count=1,
    )

    with Session(engine) as session:
        write_synthesis_seeds(
            session,
            task_id=task_id,
            synthesis=synthesis,
            quality=quality,
            warnings=["测试警告"],
        )

    target_sections = [
        "task_background",
        "paper_supplement",
        "repo_overview",
        "comparison_matrix",
        "recommendation",
        "next_steps",
    ]

    with Session(engine) as session:
        all_seeds = ReportSectionSeedRepository(session).list_by_task(task_id)

    seeds_by_key = {s.section_key: s for s in all_seeds}
    for key in target_sections:
        assert key in seeds_by_key, f"missing section: {key}"
        seed = seeds_by_key[key]
        assert seed.node == "research_synthesis"
        sd = seed.structured_data or {}
        assert "research_synthesis" in sd
        assert "research_quality" in sd
        assert sd["research_synthesis"]["thesis"] == "核心论点内容"
        assert sd["research_quality"]["research_depth"] == "medium"
        # 每个 seed 都应包含 warnings
        assert any("测试限制" in w for w in seed.warnings)


def test_write_synthesis_seeds_narrative_content(engine) -> None:
    task_id = uuid.uuid4().hex
    with Session(engine) as session:
        _seed_task_row(session, task_id)

    synthesis = ResearchSynthesis(
        thesis="此次调研的核心判断",
        key_insights=["关键发现1"],
        repo_interpretations={"repo-a": "该仓库适合快速原型"},
        tradeoffs=["速度 vs 准确性"],
        uncertainty=["部分证据较弱"],
        next_questions=["运行冒烟测试"],
        evidence_ids=[],
    )
    quality = ResearchQuality()

    with Session(engine) as session:
        write_synthesis_seeds(
            session,
            task_id=task_id,
            synthesis=synthesis,
            quality=quality,
            warnings=[],
        )

    with Session(engine) as session:
        seeds = ReportSectionSeedRepository(session).list_by_task(task_id)

    seeds_by_key = {s.section_key: s for s in seeds}

    # task_background → thesis
    assert "此次调研的核心判断" in seeds_by_key["task_background"].narrative_seed
    # paper_supplement → key_insights
    assert "关键发现1" in seeds_by_key["paper_supplement"].narrative_seed
    # repo_overview → repo_interpretations
    assert "repo-a: 该仓库适合快速原型" in seeds_by_key["repo_overview"].narrative_seed
    # comparison_matrix → tradeoffs
    assert "速度 vs 准确性" in seeds_by_key["comparison_matrix"].narrative_seed
    # next_steps → next_questions
    assert "运行冒烟测试" in seeds_by_key["next_steps"].narrative_seed


# ── build_research_synthesis_prompt ───────────────────────────────────────


def test_build_research_synthesis_prompt_contains_constraints() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id)
    digest = build_evidence_digest(context.evidence_items)
    quality = ResearchQuality()

    prompt = build_research_synthesis_prompt(context, quality, digest)

    assert "不得声称复现成功" in prompt
    assert "weak/missing" in prompt or "弱" in prompt or "缺失" in prompt
    assert "thesis" in prompt
    assert "evidence_ids" in prompt


def test_build_research_synthesis_prompt_contains_task_goal() -> None:
    task_id = uuid.uuid4().hex
    context = _make_report_context(task_id, evidence_items=[])
    digest = build_evidence_digest([])
    quality = ResearchQuality()

    prompt = build_research_synthesis_prompt(context, quality, digest)

    assert "对比 RAG 框架" in prompt


# ── ResearchQuality schema ────────────────────────────────────────────────


def test_research_quality_defaults() -> None:
    q = ResearchQuality()
    assert q.research_depth == "shallow"
    assert q.confidence_level == "low"
    assert q.evidence_coverage == 0.0
    assert q.limitations == []
    assert q.has_paperqa_answer is False
    assert q.has_web_report is False
    assert q.repo_card_count == 0


# ── PaperQAAnswerRecord schema ────────────────────────────────────────────


def test_paperqa_answer_record_defaults() -> None:
    record = PaperQAAnswerRecord(question="Q?")
    assert record.question == "Q?"
    assert record.answer == ""
    assert record.failed is False
    assert record.warning is None
    assert record.context_evidence_ids == []
