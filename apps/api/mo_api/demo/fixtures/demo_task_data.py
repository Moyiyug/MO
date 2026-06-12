"""稳定 Demo 任务预烤数据（F-014，不依赖上游在线）。"""

from __future__ import annotations

from datetime import datetime, timezone

from ...models.comparison import ComparisonMatrix, DimensionScore, RepoRanking
from ...models.enums import (
    ClaimLabel,
    EvidenceStrength,
    NodeStatus,
    SourceType,
    STATIC_REPRO_ASSESSMENT_LABEL,
    TaskStatus,
)
from ...models.evidence import EvidenceItem, ReportClaim
from ...models.events import NodeEvent
from ...models.plan import DEFAULT_RUBRIC_WEIGHTS
from ...models.repo import RepoCard
from ...models.repo_discovery import RepoCandidate
from ...models.report import REPORT_SECTION_KEYS, REPORT_SECTION_TITLES, Report, ReportSection
from ...models.reproducibility import ReproducibilityReport, ReproducibilityScore
from ...models.task import TaskPermissions

DEMO_TASK_ID = "demo_mo_task_001"
_REPO_A = "https://github.com/langchain-ai/langchain"
_REPO_B = "https://github.com/run-llama/llama_index"
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def build_demo_repo_candidates() -> list[RepoCandidate]:
    """离线 demo 候选仓库（F-014 + F-015）：无网络时也能演示自动发现。"""
    return [
        RepoCandidate(
            repo_url="https://github.com/langchain-ai/langchain",
            repo_name="langchain-ai/langchain",
            description="构建 LLM 应用的框架，提供链式编排与工具集成。",
            stars=95000,
            language="Python",
            pushed_at="2026-05-20T00:00:00Z",
            topics=["llm", "agents", "framework"],
            relevance_score=0.93,
            relevance_reason="与 LLM 应用编排目标高度相关，生态活跃。",
            discovered_by="github_search",
        ),
        RepoCandidate(
            repo_url="https://github.com/run-llama/llama_index",
            repo_name="run-llama/llama_index",
            description="面向 RAG 的数据框架，索引与检索 API 清晰。",
            stars=38000,
            language="Python",
            pushed_at="2026-05-18T00:00:00Z",
            topics=["rag", "llm", "data"],
            relevance_score=0.88,
            relevance_reason="RAG 管道与数据索引专精，文档完整。",
            discovered_by="github_search",
        ),
        RepoCandidate(
            repo_url="https://github.com/deepset-ai/haystack",
            repo_name="deepset-ai/haystack",
            description="端到端 LLM/检索编排框架。",
            stars=17000,
            language="Python",
            pushed_at="2026-05-10T00:00:00Z",
            topics=["nlp", "rag", "llm"],
            relevance_score=0.74,
            relevance_reason="支持检索与生成管道，工程成熟。",
            discovered_by="github_search",
        ),
    ]


def build_demo_bundle() -> dict:
    """构建完整 demo 数据包，供 DemoService 幂等写入。"""
    ev_repo_a = "demo_ev_repo_a_readme"
    ev_repo_b = "demo_ev_repo_b_readme"
    ev_cmp = "demo_ev_comparison"
    ev_repro = "demo_ev_repro"

    evidence = [
        EvidenceItem(
            id=ev_repo_a,
            task_id=DEMO_TASK_ID,
            source_type=SourceType.REPO_FILE,
            source_uri=_REPO_A,
            locator="README.md",
            quote_or_summary="LangChain 是用于构建 LLM 应用的框架，提供链式编排与工具集成。",
            strength=EvidenceStrength.STRONG,
            created_at=_NOW,
        ),
        EvidenceItem(
            id=ev_repo_b,
            task_id=DEMO_TASK_ID,
            source_type=SourceType.REPO_FILE,
            source_uri=_REPO_B,
            locator="README.md",
            quote_or_summary="LlamaIndex 专注数据索引与 RAG 管道，文档与示例较完整。",
            strength=EvidenceStrength.STRONG,
            created_at=_NOW,
        ),
        EvidenceItem(
            id=ev_cmp,
            task_id=DEMO_TASK_ID,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri=_REPO_A,
            locator="comparison:engineering_fit",
            quote_or_summary="对比矩阵：LangChain 生态更广，LlamaIndex RAG 专精度更高。",
            strength=EvidenceStrength.MEDIUM,
            created_at=_NOW,
        ),
        EvidenceItem(
            id=ev_repro,
            task_id=DEMO_TASK_ID,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri=_REPO_B,
            locator="repro:install_clarity",
            quote_or_summary="静态复现评估：两仓库均有 pip 安装说明与示例。",
            strength=EvidenceStrength.MEDIUM,
            created_at=_NOW,
        ),
        EvidenceItem(
            id="demo_ev_pending",
            task_id=DEMO_TASK_ID,
            source_type=SourceType.MODEL_INFERENCE,
            source_uri=_REPO_A,
            locator="paper:relationship",
            quote_or_summary="官方论文与仓库版本对应关系待用户确认。",
            strength=EvidenceStrength.WEAK,
            created_at=_NOW,
        ),
    ]

    repo_cards = [
        RepoCard(
            id="demo_card_langchain",
            task_id=DEMO_TASK_ID,
            repo_url=_REPO_A,
            repo_name="langchain",
            summary="LLM 应用编排框架，模块丰富，社区活跃。",
            primary_language="Python",
            project_type="framework",
            dependencies=["langchain-core", "pydantic"],
            entrypoints=["langchain"],
            test_commands=["python --version"],
            docs_paths=["docs/"],
            license="MIT",
            risks=["API 变更频繁"],
            evidence_ids=[ev_repo_a],
        ),
        RepoCard(
            id="demo_card_llamaindex",
            task_id=DEMO_TASK_ID,
            repo_url=_REPO_B,
            repo_name="llama_index",
            summary="面向 RAG 的数据框架，索引与检索 API 清晰。",
            primary_language="Python",
            project_type="framework",
            dependencies=["llama-index-core"],
            entrypoints=["llama_index"],
            test_commands=["python --version"],
            docs_paths=["docs/"],
            license="MIT",
            risks=["部分高级功能依赖外部服务"],
            evidence_ids=[ev_repo_b],
        ),
    ]

    comparison = ComparisonMatrix(
        id="demo_comparison",
        task_id=DEMO_TASK_ID,
        repo_urls=[_REPO_A, _REPO_B],
        weights=dict(DEFAULT_RUBRIC_WEIGHTS),
        scores=[
            DimensionScore(
                dimension="engineering_fit",
                repo_url=_REPO_A,
                score=0.82,
                rationale="生态与集成选项多，适合快速原型。",
                evidence_ids=[ev_cmp],
                label=ClaimLabel.INFERENCE,
            ),
            DimensionScore(
                dimension="engineering_fit",
                repo_url=_REPO_B,
                score=0.78,
                rationale="RAG 管道 API 一致性好。",
                evidence_ids=[ev_cmp],
                label=ClaimLabel.INFERENCE,
            ),
            DimensionScore(
                dimension="reproducibility",
                repo_url=_REPO_A,
                score=0.75,
                rationale="文档与示例覆盖安装与基础用法。",
                evidence_ids=[ev_repro],
                label=ClaimLabel.INFERENCE,
            ),
            DimensionScore(
                dimension="reproducibility",
                repo_url=_REPO_B,
                score=0.8,
                rationale="示例与 notebook 较完整。",
                evidence_ids=[ev_repro],
                label=ClaimLabel.INFERENCE,
            ),
            # 补全剩余维度占位（Demo baseline）
            *[
                DimensionScore(
                    dimension=dim,
                    repo_url=url,
                    score=0.5,
                    rationale="Demo baseline",
                    evidence_ids=[ev_cmp],
                    label=ClaimLabel.INFERENCE,
                )
                for dim in [
                    "technical_route",
                    "documentation",
                    "research_value",
                    "extensibility",
                    "risks",
                    "recommended_use_case",
                ]
                for url in [_REPO_A, _REPO_B]
            ],
        ],
        rankings=[
            RepoRanking(
                repo_url=_REPO_A,
                repo_name="langchain",
                weighted_total=0.79,
                per_dimension={"engineering_fit": 0.82, "reproducibility": 0.75},
            ),
            RepoRanking(
                repo_url=_REPO_B,
                repo_name="llama_index",
                weighted_total=0.77,
                per_dimension={"engineering_fit": 0.78, "reproducibility": 0.8},
            ),
        ],
        recommendation=(
            "若目标是快速搭建 Agent/链式应用，LangChain 更合适；"
            "若专注 RAG 与索引管道，LlamaIndex 更匹配。"
        ),
        limitations=[
            "未执行真实 smoke test，复现结论为静态评估。",
            "论文与仓库版本关系部分为 pending。",
        ],
        recommendation_evidence_ids=[ev_cmp],
        generated_at=_NOW,
    )

    reproducibility = ReproducibilityReport(
        id="demo_repro",
        task_id=DEMO_TASK_ID,
        scores=[
            ReproducibilityScore(
                repo_url=_REPO_A,
                repo_name="langchain",
                overall_score=0.74,
                dimension_scores={"install_clarity": 0.8, "documentation_quality": 0.75},
                reasons=["README 含 pip 安装说明"],
                missing_info=[],
                recommended_next_checks=["Run smoke test with user approval"],
                evidence_ids=[ev_repro],
                assessment_label=STATIC_REPRO_ASSESSMENT_LABEL,
            ),
            ReproducibilityScore(
                repo_url=_REPO_B,
                repo_name="llama_index",
                overall_score=0.78,
                dimension_scores={"install_clarity": 0.85, "documentation_quality": 0.8},
                reasons=["示例 notebook 覆盖常见场景"],
                missing_info=[],
                recommended_next_checks=["Verify GPU requirements for local models"],
                evidence_ids=[ev_repro],
                assessment_label=STATIC_REPRO_ASSESSMENT_LABEL,
            ),
        ],
        generated_at=_NOW,
    )

    claims = [
        ReportClaim(
            id="demo_claim_1",
            claim="LangChain 适合链式编排与工具集成场景。",
            label=ClaimLabel.INFERENCE,
            confidence=0.8,
            evidence_ids=[ev_repo_a, ev_cmp],
        ),
        ReportClaim(
            id="demo_claim_2",
            claim="LlamaIndex 在 RAG 索引管道上文档更聚焦。",
            label=ClaimLabel.INFERENCE,
            confidence=0.78,
            evidence_ids=[ev_repo_b, ev_cmp],
        ),
        ReportClaim(
            id="demo_claim_pending",
            claim="官方论文与当前 main 分支对应关系未完全确认。",
            label=ClaimLabel.PENDING,
            confidence=0.3,
            evidence_ids=[],
            requires_user_review=True,
        ),
    ]

    sections = [
        ReportSection(
            key=key,
            title=REPORT_SECTION_TITLES.get(key, key),
            markdown=f"## {REPORT_SECTION_TITLES.get(key, key)}\n\nDemo 离线内容（{key}）。",
            claims=claims if key == "recommendation" else [],
            is_pending=key == "risks",
        )
        for key in REPORT_SECTION_KEYS
    ]

    markdown = "\n\n".join(s.markdown for s in sections)
    report = Report(
        id="demo_report",
        task_id=DEMO_TASK_ID,
        sections=sections,
        pending_warnings=["存在 pending 论断，请人工复核论文版本关系。"],
        generated_at=_NOW,
        markdown=markdown,
    )

    node_events = [
        NodeEvent(
            task_id=DEMO_TASK_ID,
            seq=i + 1,
            node=node,
            status=NodeStatus.COMPLETED,
            output_summary=f"Demo: {node} completed",
            created_at=_NOW,
        )
        for i, node in enumerate(
            [
                "repo_ingest",
                "code_understanding",
                "paper_research",
                "reproducibility",
                "sandbox_runner",
                "comparison_builder",
            ]
        )
    ]

    return {
        "task": {
            "id": DEMO_TASK_ID,
            "goal": "【Demo】对比 LangChain 与 LlamaIndex 的工程成熟度与可复现性",
            "repo_urls": [_REPO_A, _REPO_B],
            "paper_urls": [],
            "output_language": "zh",
            "template": "github_repo_comparison",
            "permissions": TaskPermissions().model_dump(),
            "status": TaskStatus.DONE.value,
            "created_at": _NOW,
        },
        "evidence": evidence,
        "repo_cards": repo_cards,
        "comparison": comparison,
        "reproducibility": reproducibility,
        "report": report,
        "node_events": node_events,
    }
