"""报告生成服务（PRD F-011）— Report v2。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("mo_api.report")

from sqlmodel import Session

from ..adapters.model_gateway.gateway import ModelGateway, get_model_gateway
from ..models.enums import (
    CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX,
    CODE_INSIGHT_LOCATOR_EXECUTION_PATH,
    CODE_INSIGHT_LOCATOR_REPO_SUMMARY,
    CODE_INSIGHT_PREFIX_CORE_MODULE,
    STATIC_REPRO_ASSESSMENT_LABEL,
    ClaimLabel,
    EvidenceStrength,
    MaterialType,
    NodeStatus,
    SourceType,
    TaskStatus,
)
from ..models.evidence import EvidenceItem, ReportClaim
from ..models.events import NodeEvent
from ..models.plan import Plan
from ..models.report import (
    REPORT_SECTION_KEYS,
    REPORT_SECTION_TITLES,
    EvidenceAppendixGroup,
    KeyFinding,
    Report,
    ReportSection,
    ScenarioRecommendation,
)
from ..models.report_seed import ReportSectionSeed
from ..models.task import TaskResponse
from ..storage.repositories import (
    ComparisonRepository,
    EventRepository,
    EvidenceRepository,
    PlanRepository,
    ReproducibilityRepository,
    ReportRepository,
    RepoCardRepository,
    TaskRepository,
)
from .report_context import ReportContext, ReportContextService
from .report_evidence import (
    ClaimFactory,
    EvidenceDigest,
    build_evidence_digest,
    format_claim_for_markdown,
)
from .report_polish import FinalReportPolisher, SectionDraft, SectionPolisher, build_safe_deep_research_fallback
from .research_synthesis import (
    ResearchSynthesisService,
    write_synthesis_seeds,
)
from .state_machine import ensure_transition


class ReportNotReadyError(Exception):
    """任务状态尚未到达报告阶段。"""


class ReportService:
    """组装 13 段 Markdown 报告并持久化。"""

    def __init__(
        self,
        session: Session,
        *,
        gateway: ModelGateway | None = None,
    ) -> None:
        self.session = session
        self._gateway = gateway  # None → 懒加载 get_model_gateway()
        self.task_repo = TaskRepository(session)
        self.plan_repo = PlanRepository(session)
        self.event_repo = EventRepository(session)
        self.repo_card_repo = RepoCardRepository(session)
        self.evidence_repo = EvidenceRepository(session)
        self.report_repo = ReportRepository(session)
        self.comparison_repo = ComparisonRepository(session)
        self.repro_repo = ReproducibilityRepository(session)

    def _ensure_gateway(self) -> ModelGateway:
        if self._gateway is None:
            self._gateway = get_model_gateway()
        return self._gateway

    def _seeds_by_section(
        self,
        context: ReportContext,
    ) -> dict[str, list[ReportSectionSeed]]:
        grouped: dict[str, list[ReportSectionSeed]] = {}
        for seed in context.report_seeds:
            grouped.setdefault(seed.section_key, []).append(seed)
        return grouped

    def _section_to_draft(
        self,
        section: ReportSection,
        *,
        seeds: list[ReportSectionSeed],
    ) -> SectionDraft:
        seed_narratives = [seed.narrative_seed for seed in seeds if seed.narrative_seed]
        seed_structured = [
            seed.structured_data for seed in seeds if seed.structured_data
        ]
        seed_warnings = [
            warning for seed in seeds for warning in seed.warnings
        ]
        metadata = dict(section.metadata or {})
        metadata["seed_structured_data"] = seed_structured
        metadata["seed_warnings"] = seed_warnings
        metadata["seed_nodes"] = [seed.node for seed in seeds]
        return SectionDraft(
            key=section.key,
            title=section.title,
            structured_markdown=section.markdown,
            seed_narratives=seed_narratives,
            claims=section.claims,
            evidence_ids=list(section.evidence_ids or []),
            metadata=metadata,
            is_pending=section.is_pending,
            summary=section.summary,
        )

    def get_cached_report(self, task_id: str) -> Report | None:
        self._require_reportable_task(task_id)
        return self.report_repo.get_by_task(task_id)

    def advance_to_review_if_draft(self, task_id: str) -> None:
        """将 REPORT_DRAFT 推进到 REVIEW_REQUIRED（幂等）。"""
        task = self.task_repo.get(task_id)
        if task is not None and task.status is TaskStatus.REPORT_DRAFT:
            self._advance_to_review(task_id, task.status)

    async def generate_async(
        self, task_id: str, *, advance_status: bool = True
    ) -> Report:
        task = self._require_reportable_task(task_id)

        # v2: 聚合上下文
        context = ReportContextService(self.session).build(task_id)
        plan = context.plan
        events = context.events
        repo_cards = context.repo_cards
        evidence_items = context.evidence_items
        comparison = context.comparison
        reproducibility = context.reproducibility

        code_insights = self._derive_code_insights(evidence_items)
        evidence_digest = build_evidence_digest(evidence_items)
        claim_factory = ClaimFactory(evidence_digest)

        pending_warnings: list[str] = []

        # 研究综合（PRD F4 / F8）
        synthesis = None
        quality = None
        synthesis_warnings: list[str] = []
        try:
            synthesis, quality, synthesis_warnings = await ResearchSynthesisService(
                self._ensure_gateway()
            ).synthesize(context, evidence_digest=evidence_digest)
            if synthesis_warnings:
                pending_warnings.extend(synthesis_warnings)
            # 写入 synthesis seeds
            write_synthesis_seeds(
                self.session,
                task_id=task_id,
                synthesis=synthesis,
                quality=quality,
                warnings=synthesis_warnings,
            )
            # 重新构建 context，确保刚写入的 synthesis seed 被 SectionPolisher 读取
            context = ReportContextService(self.session).build(task_id)
        except Exception as exc:
            logger.warning("ResearchSynthesisService failed, continuing: %s", exc)
            pending_warnings.append(f"研究综合失败（{str(exc)[:120]}），报告仍基于原始章节生成。")
            synthesis = None
            quality = None

        # v2: 统一 kwargs，注入 digest / claim_factory / comparison / reproducibility
        kwargs: dict[str, Any] = dict(
            task=task,
            plan=plan,
            events=events,
            repo_cards=repo_cards,
            evidence_items=evidence_items,
            evidence_digest=evidence_digest,
            claim_factory=claim_factory,
            comparison=comparison,
            reproducibility=reproducibility,
        )

        sync_builders: list[Any] = [
            self._section_task_background,
            self._section_user_boundaries,
            self._section_approved_plan,
            self._section_repo_overview,
            self._section_paper_supplement,
            self._section_comparison_matrix,
            self._section_reproducibility,
            self._section_risks,
            self._section_recommendation,
            self._section_next_steps,
            self._section_evidence_references,
        ]
        sync_keys = [
            "task_background",
            "user_boundaries",
            "approved_plan",
            "repo_overview",
            "paper_supplement",
            "comparison_matrix",
            "reproducibility",
            "risks",
            "recommendation",
            "next_steps",
            "evidence_references",
        ]

        section_map: dict[str, ReportSection] = {}
        for key, builder in zip(sync_keys, sync_builders, strict=True):
            section, warnings = builder(**kwargs)
            section_map[key] = section
            pending_warnings.extend(warnings)

        exec_section, exec_warnings = await self._section_execution_summary(
            task=task,
            events=events,
            evidence_items=evidence_items,
            evidence_digest=evidence_digest,
            claim_factory=claim_factory,
        )
        section_map["execution_summary"] = exec_section
        pending_warnings.extend(exec_warnings)

        tech_section, tech_warnings = await self._section_technical_route(
            task=task,
            repo_cards=repo_cards,
            evidence_items=evidence_items,
            evidence_digest=evidence_digest,
            claim_factory=claim_factory,
            code_insights=code_insights,
        )
        section_map["technical_route"] = tech_section
        pending_warnings.extend(tech_warnings)

        raw_sections = [section_map[key] for key in REPORT_SECTION_KEYS]

        seeds_by_section = self._seeds_by_section(context)
        section_polisher = SectionPolisher(self._ensure_gateway())
        sections: list[ReportSection] = []
        polish_warnings: list[str] = []

        for raw_section in raw_sections:
            draft = self._section_to_draft(
                raw_section,
                seeds=seeds_by_section.get(raw_section.key, []),
            )
            polished = await section_polisher.polish(
                draft,
                output_language=task.output_language.value,
            )
            polish_warnings.extend(polished.warnings)
            metadata = dict(draft.metadata or {})
            metadata["structured_markdown"] = draft.structured_markdown
            metadata["seed_narratives"] = draft.seed_narratives
            metadata["polish_status"] = polished.polish_status
            metadata["polish_warnings"] = polished.warnings
            sections.append(
                ReportSection(
                    key=draft.key,
                    title=draft.title,
                    markdown=self._strip_duplicate_section_heading(
                        polished.reader_markdown,
                        draft.title,
                    ),
                    claims=draft.claims,
                    is_pending=draft.is_pending,
                    summary=polished.summary,
                    evidence_ids=draft.evidence_ids,
                    metadata=metadata,
                )
            )
        pending_warnings.extend(
            warning
            for warning in polish_warnings
            if not warning.startswith("section polish fallback:")
        )

        # v2: 构建 executive summary 和 key findings
        executive_summary = self._build_executive_summary(context, evidence_digest)
        key_findings = self._build_key_findings(sections, evidence_digest)
        scenario_recs = self._build_scenario_recommendations(comparison, evidence_digest)
        appendix_groups = self._build_evidence_appendix_groups(evidence_items, evidence_digest)

        unique_pending_warnings = list(dict.fromkeys(pending_warnings))
        safe_fallback_markdown = build_safe_deep_research_fallback(
            synthesis=synthesis,
            quality=quality,
            pending_warnings=unique_pending_warnings,
        )
        markdown = await FinalReportPolisher(self._ensure_gateway()).polish_report(
            executive_summary=executive_summary,
            sections=sections,
            pending_warnings=unique_pending_warnings,
            output_language=task.output_language.value,
            fallback_markdown=safe_fallback_markdown,
            research_synthesis=synthesis,
            research_quality=quality,
        )
        report = Report(
            id=uuid.uuid4().hex,
            task_id=task_id,
            sections=sections,
            pending_warnings=unique_pending_warnings,
            generated_at=datetime.now(timezone.utc),
            markdown=markdown,
            executive_summary=executive_summary,
            key_findings=key_findings,
            recommendation_summary=scenario_recs,
            evidence_appendix_groups=appendix_groups,
            report_version="v2",
            research_synthesis=synthesis,
            research_quality=quality,
        )
        saved = self.report_repo.upsert_by_task(report)
        if advance_status:
            self._advance_to_review(task_id, task.status)
        return saved

    def confirm_report(self, task_id: str) -> TaskStatus:
        task = self.task_repo.get(task_id)
        if task is None:
            raise ValueError("task not found")
        if task.status is not TaskStatus.REVIEW_REQUIRED:
            raise ValueError(f"cannot confirm from status {task.status.value}")
        if self.report_repo.get_by_task(task_id) is None:
            raise ValueError("report not found")
        ensure_transition(task.status, TaskStatus.DONE)
        updated = self.task_repo.update_status(task_id, TaskStatus.DONE)
        assert updated is not None
        return updated.status

    def _advance_to_review(self, task_id: str, current: TaskStatus) -> None:
        if current is TaskStatus.REPORT_DRAFT:
            ensure_transition(current, TaskStatus.REVIEW_REQUIRED)
            self.task_repo.update_status(task_id, TaskStatus.REVIEW_REQUIRED)

    def _require_reportable_task(self, task_id: str) -> TaskResponse:
        task = self.task_repo.get(task_id)
        if task is None:
            raise ValueError("task not found")
        allowed = {
            TaskStatus.REPORT_DRAFT,
            TaskStatus.REVIEW_REQUIRED,
            TaskStatus.DONE,
        }
        if task.status not in allowed:
            raise ReportNotReadyError(
                f"task status {task.status.value} is not reportable"
            )
        return task

    @staticmethod
    def _title(key: str, lang: str) -> str:
        if lang == "en":
            en_titles = {
                "task_background": "1. Task Background",
                "user_boundaries": "2. User-Confirmed Boundaries",
                "approved_plan": "3. Approved Plan",
                "execution_summary": "4. Execution Summary",
                "repo_overview": "5. Repository Overview",
                "paper_supplement": "6. Paper / Context Supplement",
                "technical_route": "7. Technical Route Analysis",
                "comparison_matrix": "8. Comparison Matrix",
                "reproducibility": "9. Reproducibility Analysis",
                "risks": "10. Risks and Uncertainties",
                "recommendation": "11. Recommendation and Scenarios",
                "next_steps": "12. Next Steps",
                "evidence_references": "13. Evidence and References",
            }
            return en_titles.get(key, REPORT_SECTION_TITLES.get(key, key))
        return REPORT_SECTION_TITLES.get(key, key)

    @staticmethod
    def _evidence_to_label(item: EvidenceItem) -> ClaimLabel:
        if item.source_type is SourceType.USER_CONFIRMATION:
            return ClaimLabel.FACT
        if item.source_type is SourceType.REPO_FILE:
            if item.strength is EvidenceStrength.STRONG:
                return ClaimLabel.FACT
            return ClaimLabel.INFERENCE
        if item.source_type is SourceType.MODEL_INFERENCE:
            return ClaimLabel.INFERENCE
        if item.strength is EvidenceStrength.MISSING:
            return ClaimLabel.PENDING
        return ClaimLabel.INFERENCE

    def _make_claim(
        self,
        claim_text: str,
        label: ClaimLabel,
        evidence_ids: list[str],
        *,
        requires_user_review: bool = False,
    ) -> ReportClaim:
        eids = list(evidence_ids)
        if not eids and label is not ClaimLabel.PENDING:
            label = ClaimLabel.PENDING
        return ReportClaim(
            id=uuid.uuid4().hex,
            claim=claim_text,
            label=label,
            evidence_ids=eids,
            requires_user_review=requires_user_review,
        )

    def _format_claim_line(
        self,
        claim: ReportClaim,
        *,
        digest: EvidenceDigest | None = None,
    ) -> str:
        """v2: 使用友好证据编号（E01/E02），不暴露 raw evidence id 在正文。"""
        return format_claim_for_markdown(claim, digest=digest, lang="zh")

    @staticmethod
    def _clean_comparison_rationale(rationale: str | None) -> str:
        text = (rationale or "").strip()
        if not text:
            return "评分理由不足，需人工复核。"
        if text.startswith("{") or '"score"' in text or "'score'" in text:
            return "模型评分理由不完整，已按保守结果展示，需人工复核。"
        text = (
            text.replace("project_type=yes", "type=1")
            .replace("project_type=no", "type=0")
            .replace("project_type_present=", "type=")
            .replace("license_present=", "license=")
            .replace("ĄŁ", ".")
        )
        if len(text) > 96:
            return text[:93].rstrip() + "..."
        return text

    @staticmethod
    def _clean_reference_summary(summary: str | None) -> str:
        text = (summary or "").strip()
        if not text:
            return "（无摘要）"
        if '"score"' in text or "'score'" in text or '{"score"' in text:
            prefix = text.split(":", 1)[0] if ":" in text else "模型评分"
            return f"{prefix}: 模型评分原始输出已压缩，需人工复核。"
        text = (
            text.replace("project_type_present=", "type=")
            .replace("license_present=", "license=")
            .replace("project_type=", "type=")
            .replace("ĄŁ", ".")
        )
        if len(text) > 240:
            return text[:237].rstrip() + "..."
        return text

    @staticmethod
    def _strip_duplicate_section_heading(markdown: str, title: str) -> str:
        lines = (markdown or "").strip().splitlines()
        if not lines:
            return ""
        first = lines[0].strip()
        normalized = first.lstrip("#").strip()
        if first.startswith("#") and normalized == title.strip():
            return "\n".join(lines[1:]).strip()
        return "\n".join(lines).strip()

    def _assemble_markdown(self, sections: list[ReportSection]) -> str:
        """保留旧签名兼容性。"""
        return self._assemble_markdown_v2(sections)

    def _assemble_markdown_v2(
        self,
        sections: list[ReportSection],
        *,
        executive_summary: str | None = None,
        pending_warnings: list[str] | None = None,
    ) -> str:
        """v2: 报告 Markdown 带 executive summary + pending warnings header。"""
        parts: list[str] = []
        if executive_summary:
            parts.append("# MO 调研报告\n")
            parts.append(executive_summary.strip())
            parts.append("")
        if pending_warnings:
            parts.append("> **待确认提醒**")
            for w in pending_warnings[:10]:
                parts.append(f"> - {w}")
            parts.append("")
        for section in sections:
            parts.append(f"## {section.title}\n")
            if section.summary:
                parts.append(f"> {section.summary}\n")
            if section.is_pending:
                parts.append("> **[pending]** 本节包含待确认信息。\n")
            parts.append(section.markdown.strip())
            parts.append("")
        return "\n".join(parts).strip() + "\n"

    # ── v2 helpers ──────────────────────────────────────────────

    def _build_executive_summary(
        self,
        context: ReportContext,
        digest: EvidenceDigest,
    ) -> str:
        """生成面向人的执行摘要。"""
        task = context.task
        repo_names = [c.repo_name for c in context.repo_cards]
        repo_list = ", ".join(repo_names) if repo_names else "（无仓库）"
        n_evidence = len(digest.refs)
        n_weak = len(digest.weak_or_missing_ids)
        lines = [
            f"本次调研围绕「{task.goal}」展开，共分析 {len(context.repo_cards)} 个仓库，",
            f"收集 {n_evidence} 条证据。",
        ]
        if n_weak:
            lines.append(f"其中 {n_weak} 条证据较弱或缺失，对应结论标注为待确认。")
        lines.append(f"\n调研对象：{repo_list}")
        return "".join(lines)

    def _build_key_findings(
        self,
        sections: list[ReportSection],
        digest: EvidenceDigest,
    ) -> list[KeyFinding]:
        """从各章节 claim 中抽取关键发现。"""
        findings: list[KeyFinding] = []
        for section in sections:
            # 每章取前 2 个非 pending claim 作为关键发现
            for claim in section.claims[:2]:
                if claim.label is ClaimLabel.PENDING:
                    continue
                findings.append(
                    KeyFinding(
                        title=section.title,
                        summary=claim.claim[:500],
                        label=claim.label,
                        evidence_ids=list(claim.evidence_ids),
                        requires_user_review=claim.requires_user_review,
                    )
                )
        return findings[:10]

    def _build_scenario_recommendations(
        self,
        comparison: object | None,
        digest: EvidenceDigest,
    ) -> list[ScenarioRecommendation]:
        """从对比矩阵构建场景化推荐。"""
        from ..models.comparison import ComparisonMatrix

        recs: list[ScenarioRecommendation] = []
        if isinstance(comparison, ComparisonMatrix) and comparison.rankings:
            top = comparison.rankings[0] if comparison.rankings else None
            top_name = top.repo_name if top else "未知"
            for scenario, rationale in [
                (
                    "快速 demo",
                    f"建议从 {top_name} 开始，其文档与入口最清晰，适合快速了解。",
                ),
                (
                    "论文复现",
                    "需检查论文关系是否明确、安装步骤是否完整。",
                ),
                (
                    "工程集成",
                    "关注依赖复杂度、License 兼容性和代码模块化程度。",
                ),
                (
                    "二次开发",
                    "关注架构模块化、扩展性和社区活跃度。",
                ),
            ]:
                recs.append(
                    ScenarioRecommendation(
                        scenario=scenario,
                        recommendation=rationale,
                        rationale=rationale,
                        evidence_ids=list(comparison.recommendation_evidence_ids),
                        requires_user_review=True,
                    )
                )
            return recs
        # 无对比矩阵时返回 pending 场景
        for scenario in ["快速 demo", "论文复现", "工程集成", "二次开发"]:
            recs.append(
                ScenarioRecommendation(
                    scenario=scenario,
                    recommendation="待生成对比矩阵后评估",
                    rationale="暂无对比数据",
                    evidence_ids=[],
                    requires_user_review=True,
                )
            )
        return recs

    def _build_evidence_appendix_groups(
        self,
        evidence_items: list[EvidenceItem],
        digest: EvidenceDigest,
    ) -> list[EvidenceAppendixGroup]:
        """按 source_type 分组构建证据附录。"""
        groups: list[EvidenceAppendixGroup] = []
        group_keys = [
            ("repo_file", "仓库文件证据"),
            ("paper", "论文 / 文档"),
            ("web", "网络资料"),
            ("run_log", "运行日志"),
            ("user_confirmation", "用户确认"),
            ("model_inference", "模型推断"),
        ]
        for key, title in group_keys:
            refs = digest.by_source_type.get(key, [])
            if refs:
                groups.append(
                    EvidenceAppendixGroup(
                        key=key,
                        title=title,
                        evidence_ids=[r.evidence_id for r in refs],
                    )
                )
        return groups

    def _derive_code_insights(
        self, evidence_items: list[EvidenceItem]
    ) -> list[dict[str, Any]]:
        """从 evidence 中提取代码洞察，使用共享常量匹配 locator。

        常量定义在 models/enums.py，与 code_understanding 节点共享。
        """
        insights: list[dict[str, Any]] = []
        for item in evidence_items:
            if item.source_type is not SourceType.MODEL_INFERENCE:
                continue
            loc = item.locator or ""
            if loc == CODE_INSIGHT_LOCATOR_EXECUTION_PATH:
                insights.append(
                    {
                        "type": "execution_path",
                        "path": item.quote_or_summary,
                        "evidence_id": item.id,
                    }
                )
            elif loc.startswith(CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX):
                module = loc[len(CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX):]
                insights.append(
                    {
                        "type": "core_module",
                        "module": module,
                        "evidence_id": item.id,
                    }
                )
            # CODE_INSIGHT_LOCATOR_REPO_SUMMARY items are skipped here
            # (handled in _section_repo_overview via RepoCard)
        return insights

    def _section_task_background(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        repo_display = ", ".join(task.repo_urls) if task.repo_urls else "（无，依赖系统推荐）"
        lines = [
            f"本次调研围绕「{task.goal}」展开，目标是帮助用户理解候选仓库的功能定位、技术路线、复现难度和适用场景。",
            "",
            f"**调研对象：** {repo_display}",
        ]
        if task.paper_urls:
            lines.append(f"**论文链接：** {', '.join(task.paper_urls)}")
        if task.template:
            lines.append(f"**模板：** {task.template}")

        # 用户输入的目标是确定性事实（来源 TaskTable）
        # F-014: 使用 find_or_create 防止重复生成证据
        existing_bg = self.evidence_repo.find_by_locator(
            task.task_id, f"task:{task.task_id}", "task.goal"
        )
        if existing_bg is not None:
            bg_evidence = existing_bg
        else:
            bg_evidence = EvidenceItem(
                id=uuid.uuid4().hex,
                task_id=task.task_id,
                source_type=SourceType.USER_CONFIRMATION,
                source_uri=f"task:{task.task_id}",
                locator="task.goal",
                quote_or_summary=task.goal[:2000],
                strength=EvidenceStrength.STRONG,
                created_at=datetime.now(timezone.utc),
            )
            self.evidence_repo.create(bg_evidence)
        # 将动态创建的 evidence 注册到 digest 以便 ClaimFactory 校验
        digest.add_item(bg_evidence)
        claims = [
            cf.make(
                f"调研目标：{task.goal}",
                ClaimLabel.FACT,
                [bg_evidence.id],
            )
        ]
        return (
            ReportSection(
                key="task_background",
                title=self._title("task_background", lang),
                markdown="\n".join(lines),
                claims=claims,
                evidence_ids=[bg_evidence.id],
            ),
            [],
        )

    def _section_user_boundaries(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)
        boundaries = list(plan.confirmed_context) if plan else []
        # v2: 添加权限摘要
        perm_summary = []
        perms = task.permissions
        if isinstance(perms, dict):
            perm_map = {
                "allow_web_search": "联网搜索",
                "allow_repo_clone": "仓库克隆",
                "allow_smoke_test": "冒烟测试",
                "allow_dependency_install": "依赖安装",
                "has_gpu": "GPU 可用",
                "max_runtime_minutes": "最大运行时间",
            }
            for key, label in perm_map.items():
                val = perms.get(key)
                if isinstance(val, bool):
                    perm_summary.append(f"- {label}：{'✅ 允许' if val else '❌ 关闭'}")
                elif isinstance(val, (int, float)) and key == "max_runtime_minutes":
                    perm_summary.append(f"- {label}：{val} 分钟")
        perm_text = "\n".join(perm_summary) or "- 使用默认权限配置"

        if not boundaries:
            md = f"**权限配置：**\n{perm_text}\n\n（暂无用户确认边界）"
            claims = [
                cf.make("用户确认边界尚未记录", ClaimLabel.PENDING, [])
            ]
            return (
                ReportSection(
                    key="user_boundaries",
                    title=self._title("user_boundaries", lang),
                    markdown=md,
                    claims=claims,
                    is_pending=True,
                ),
                ["用户确认边界尚未记录"],
            )

        # 已确认边界是用户确认的事实
        lines: list[str] = [f"**权限配置：**\n{perm_text}\n", "**已确认边界：**"]
        claims = []
        for b in boundaries:
            # F-014: 使用 find_or_create 防止重复生成证据
            existing_ev = self.evidence_repo.find_by_locator(
                task.task_id,
                f"plan:{plan.id}" if plan else f"task:{task.task_id}",
                "plan.confirmed_context",
            )
            if existing_ev is not None:
                ev = existing_ev
            else:
                ev = EvidenceItem(
                    id=uuid.uuid4().hex,
                    task_id=task.task_id,
                    source_type=SourceType.USER_CONFIRMATION,
                    source_uri=f"plan:{plan.id}" if plan else f"task:{task.task_id}",
                    locator="plan.confirmed_context",
                    quote_or_summary=b[:2000],
                    strength=EvidenceStrength.STRONG,
                    created_at=datetime.now(timezone.utc),
                )
                self.evidence_repo.create(ev)
            digest.add_item(ev)
            claim = cf.make(b, ClaimLabel.FACT, [ev.id])
            claims.append(claim)
            lines.append(self._format_claim_line(claim, digest=digest))
        return (
            ReportSection(
                key="user_boundaries",
                title=self._title("user_boundaries", lang),
                markdown="\n".join(lines),
                claims=claims,
            ),
            [],
        )

    def _section_approved_plan(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)
        if plan is None:
            return (
                ReportSection(
                    key="approved_plan",
                    title=self._title("approved_plan", lang),
                    markdown="（计划尚未生成）",
                    claims=[cf.make("计划尚未生成", ClaimLabel.PENDING, [])],
                    is_pending=True,
                ),
                ["已批准计划缺失"],
            )
        # v2: 用业务语言描述计划，不暴露 tool enum
        tool_labels = {
            "repo_ingest": "读取仓库资料",
            "code_understanding": "分析代码结构",
            "paper_research": "论文与资料调研",
            "repro_eval": "评估复现难度",
            "comparison": "对比分析",
            "critic_review": "批评审阅",
            "report_writer": "报告撰写",
            "sandbox_runner": "沙箱执行",
        }
        lines = [f"**调研摘要：** {plan.task_summary}", "", "**计划步骤：**"]
        claims: list[ReportClaim] = []
        step_meta = []
        for i, step in enumerate(plan.proposed_steps, 1):
            tool_label = tool_labels.get(step.tool.value, step.tool.value)
            risk_label = {"low": "低", "medium": "中", "high": "高"}.get(
                step.risk_level.value, step.risk_level.value
            )
            line = f"{i}. {step.title}——{tool_label}（风险：{risk_label}）"
            lines.append(line)
            claims.append(
                cf.make(
                    f"计划步骤：{step.title}",
                    ClaimLabel.PENDING,
                    [],
                )
            )
            step_meta.append(step.model_dump(mode="json"))
        return (
            ReportSection(
                key="approved_plan",
                title=self._title("approved_plan", lang),
                markdown="\n".join(lines),
                claims=claims,
                metadata={"plan_steps": step_meta},
            ),
            [],
        )

    async def _section_execution_summary(
        self,
        *,
        task: TaskResponse,
        events: list[NodeEvent],
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        # 统计完成/失败/跳过
        failed = [e for e in events if e.status is NodeStatus.FAILED]
        skipped = [e for e in events if e.status is NodeStatus.SKIPPED]
        skipped_nodes = {e.node for e in skipped}
        completed = [
            e
            for e in events
            if e.status in (NodeStatus.COMPLETED,) and e.node not in skipped_nodes
        ]
        has_run_log = any(e.source_type is SourceType.RUN_LOG for e in evidence_items)
        node_labels = {
            "task_intake": "任务录入",
            "plan_builder": "计划制定",
            "user_clarification": "用户澄清",
            "repo_ingest": "仓库资料读取",
            "code_understanding": "代码结构分析",
            "paper_research": "论文与资料调研",
            "reproducibility_analysis": "复现难度评估",
            "comparison_builder": "对比分析",
            "critic_review": "批评审阅",
            "report_writer": "报告撰写",
            "sandbox_runner": "沙箱执行",
        }

        lines = [
            "本次执行完成了仓库读取、代码结构分析、资料补充、复现性静态评估和对比分析。",
            "",
        ]
        if not has_run_log:
            lines.append(
                "> 说明：本次未记录 run_log，复现相关内容仅代表静态复现性评估，不代表实际运行或复现成功。"
            )
            lines.append("")
        if completed:
            lines.append(f"**完成项：** {', '.join(node_labels.get(e.node, e.node) for e in completed[:10])}")
        if failed:
            lines.append(f"**失败项：** {', '.join(node_labels.get(e.node, e.node) for e in failed)}")
        if skipped:
            lines.append(f"**跳过项：** {', '.join(node_labels.get(e.node, e.node) for e in skipped)}")
        lines.append("")

        # 保留原始事件在 metadata 中
        event_meta = []
        all_evidence_ids: list[str] = []
        for ev in events:
            status_val = ev.status.value if isinstance(ev.status, NodeStatus) else str(ev.status)
            event_meta.append({"node": ev.node, "status": status_val})
            all_evidence_ids.extend(ev.evidence_ids or [])

        # LLM 叙述（可选，失败不阻塞）
        event_text = "\n".join(
            f"- {node_labels.get(ev.node, ev.node)}: {ev.status.value if isinstance(ev.status, NodeStatus) else ev.status}"
            for ev in events
        ) or "（无执行事件）"
        gateway = self._ensure_gateway()
        profile = gateway.select(need_reasoning=True, long_context=True)
        if lang == "en":
            prompt = (
                "Write a concise execution summary paragraph based ONLY on the node events below. "
                "Do not invent facts. If run_log_present is false, do not say that any "
                "repository was actually run, reproduced, or verified by execution.\n\n"
                f"run_log_present: {has_run_log}\n"
                f"Events:\n{event_text}"
            )
        else:
            prompt = (
                "根据以下节点执行事件，用中文写一段简洁的执行摘要。只能基于给定事件，不得编造。"
                "如果 run_log_present 为 false，不得声称仓库已实际运行、复现成功、实测通过或运行后完成。\n\n"
                f"run_log_present: {has_run_log}\n"
                f"事件：\n{event_text}"
            )
        narrative = ""
        try:
            narrative = await gateway.complete(
                profile,
                [{"role": "user", "content": prompt}],
                max_tokens=512,
            )
        except Exception as exc:
            logger.warning("execution_summary LLM failed: %s", exc)
            narrative = "（执行摘要生成失败——原始事件见附录）"

        if narrative and not has_run_log:
            for forbidden in (
                "复现成功",
                "实际运行成功",
                "实测通过",
                "运行后完成",
                "已实际运行",
            ):
                narrative = narrative.replace(forbidden, "完成静态复现性评估")

        lines.append(narrative.strip())
        claims = [
            cf.make(
                narrative.strip() or "执行摘要",
                ClaimLabel.INFERENCE if narrative else ClaimLabel.PENDING,
                list(dict.fromkeys(all_evidence_ids)) if narrative else [],
            )
        ]
        return (
            ReportSection(
                key="execution_summary",
                title=self._title("execution_summary", lang),
                markdown="\n".join(lines),
                claims=claims,
                evidence_ids=list(dict.fromkeys(all_evidence_ids)),
                metadata={"node_events": event_meta},
            ),
            [],
        )

    def _section_repo_overview(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        comparison: Any = None,
        reproducibility: Any = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)
        if not repo_cards:
            return (
                ReportSection(
                    key="repo_overview",
                    title=self._title("repo_overview", lang),
                    markdown="（尚未摄取仓库）",
                    claims=[
                        cf.make("仓库概览尚未生成", ClaimLabel.PENDING, [])
                    ],
                    is_pending=True,
                ),
                ["仓库概览数据缺失"],
            )
        lines: list[str] = []
        claims: list[ReportClaim] = []
        evidence_by_id = {e.id: e for e in evidence_items}

        # v2: 每个仓库回答五件事：是什么、解决什么问题、技术栈、入口/测试、成熟度
        for card in repo_cards:
            name = card.repo_name or card.repo_url
            lines.append(f"### {name}")
            # 一句话定位
            lines.append(f"**仓库定位：** {card.summary[:200] if card.summary else '待分析'}")
            lines.append("")
            # 技术栈与入口
            lines.append(f"- **主要语言：** {card.primary_language or 'unknown'}")
            lines.append(f"- **项目类型：** {card.project_type or 'unknown'}")
            lines.append(f"- **关键依赖：** {', '.join(card.dependencies[:10]) or '未识别'}")
            lines.append(f"- **入口文件：** {', '.join(card.entrypoints[:8]) or '未识别'}")
            if card.test_commands:
                lines.append(f"- **测试命令：** {', '.join(card.test_commands[:5])}")
            if card.docs_paths:
                lines.append(f"- **文档路径：** {', '.join(card.docs_paths[:5])}")
            if card.license:
                lines.append(f"- **License：** {card.license}")
            # 证据引用（使用友好编号）
            label_refs = []
            for eid in card.evidence_ids[:5]:
                ref = digest.by_id.get(eid)
                if ref:
                    label_refs.append(f"{ref.display_id}({ref.strength.value})")
            if label_refs:
                lines.append(f"- **相关证据：** {', '.join(label_refs)}")
            lines.append("")

            for eid in card.evidence_ids[:3]:
                ev = evidence_by_id.get(eid)
                if ev:
                    label = self._evidence_to_label(ev)
                    claim = cf.make(ev.quote_or_summary[:200], label, [eid])
                    claims.append(claim)
        return (
            ReportSection(
                key="repo_overview",
                title=self._title("repo_overview", lang),
                markdown="\n".join(lines).strip(),
                claims=claims,
                evidence_ids=list(card.evidence_ids),
            ),
            [],
        )

    def _section_paper_supplement(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)
        research_evidence = [
            e
            for e in evidence_items
            if e.source_type in (SourceType.PAPER, SourceType.WEB)
            or e.material_type is not None
        ]
        if not research_evidence:
            claim = cf.make(
                "论文/网络调研尚未执行",
                ClaimLabel.PENDING,
                [],
            )
            return (
                ReportSection(
                    key="paper_supplement",
                    title=self._title("paper_supplement", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                ["论文/上下文补充尚未完成"],
            )

        groups: dict[str, list[EvidenceItem]] = {
            "official": [],
            "background": [],
            "pending": [],
        }
        for ev in research_evidence:
            mt = ev.material_type
            if mt in (
                MaterialType.OFFICIAL_REPO_PAPER,
                MaterialType.OFFICIAL_DOC,
            ):
                groups["official"].append(ev)
            elif mt is MaterialType.UNVERIFIED_REFERENCE or mt is None:
                groups["pending"].append(ev)
            else:
                groups["background"].append(ev)

        lines: list[str] = []
        claims: list[ReportClaim] = []
        warnings: list[str] = []

        if groups["official"]:
            lines.append("**官方论文/文档：**")
            for ev in groups["official"]:
                label = (
                    ClaimLabel.FACT
                    if ev.strength is EvidenceStrength.STRONG
                    else ClaimLabel.INFERENCE
                )
                c = self._make_claim(
                    ev.quote_or_summary[:200],
                    label,
                    [ev.id],
                )
                claims.append(c)
                lines.append(
                    f"- [{ev.material_type.value if ev.material_type else 'paper'}] "
                    f"{ev.source_uri}: {ev.quote_or_summary[:120]}"
                )
                lines.append(self._format_claim_line(c))

        if groups["background"]:
            lines.append("\n**背景引用：**")
            for ev in groups["background"]:
                c = self._make_claim(
                    ev.quote_or_summary[:200],
                    ClaimLabel.INFERENCE,
                    [ev.id],
                )
                claims.append(c)
                lines.append(self._format_claim_line(c))

        if groups["pending"]:
            lines.append("\n**待核实资料：**")
            warnings.append(f"有 {len(groups['pending'])} 项资料关系不明或待核实")
            for ev in groups["pending"]:
                c = self._make_claim(
                    ev.quote_or_summary[:200],
                    ClaimLabel.PENDING,
                    [],
                )
                claims.append(c)
                lines.append(self._format_claim_line(c))

        return (
            ReportSection(
                key="paper_supplement",
                title=self._title("paper_supplement", lang),
                markdown="\n".join(lines),
                claims=claims,
                is_pending=bool(groups["pending"]),
            ),
            warnings,
        )

    async def _section_technical_route(
        self,
        *,
        task: TaskResponse,
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        code_insights: list[dict[str, Any]],
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        if not repo_cards:
            claim = cf.make("技术路线分析数据不足", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="technical_route",
                    title=self._title("technical_route", lang),
                    markdown=self._format_claim_line(claim, digest=digest),
                    claims=[claim],
                    is_pending=True,
                ),
                ["技术路线分析证据不足"],
            )

        lines: list[str] = []
        claims: list[ReportClaim] = []
        section_eids: list[str] = []

        # v2: 使用 repo_cards 的结构化字段替代 raw insight dump
        for card in repo_cards:
            name = card.repo_name or card.repo_url
            lines.append(f"### {name} 架构要点")
            lines.append("")

            # 核心模块从 code_insights 提取
            repo_insights = [
                ins for ins in code_insights
                if ins.get("evidence_id") in card.evidence_ids
            ]
            core_modules = [
                ins.get("module") for ins in repo_insights
                if ins.get("type") == "core_module"
            ]
            exec_paths = [
                ins.get("path") for ins in repo_insights
                if ins.get("type") == "execution_path"
            ]

            lines.append(f"- **主要语言：** {card.primary_language or 'unknown'}")
            lines.append(f"- **项目类型：** {card.project_type or 'unknown'}")

            if core_modules:
                lines.append(f"- **核心模块：** {', '.join(core_modules[:8])}")
            else:
                lines.append(f"- **入口文件：** {', '.join(card.entrypoints[:8]) or '未识别'}")

            if exec_paths:
                lines.append(f"- **执行路径：** {', '.join(exec_paths[:3])}")

            if card.dependencies:
                lines.append(f"- **关键依赖：** {', '.join(card.dependencies[:10])}")

            if card.docs_paths:
                lines.append(f"- **文档路径：** {', '.join(card.docs_paths[:5])}")

            lines.append("")

            # 证据引用
            for eid in card.evidence_ids[:3]:
                ref = digest.by_id.get(eid)
                if ref:
                    section_eids.append(eid)
                    lines.append(
                        f"  {self._format_claim_line(cf.make(ref.summary[:200], ClaimLabel.INFERENCE, [eid]), digest=digest)}"
                    )
            lines.append("")

        # LLM 合成整体技术路线概述（可选，失败不阻塞）
        gateway = self._ensure_gateway()
        profile = gateway.select(need_reasoning=True, long_context=True)
        route_context = "\n".join(
            f"{card.repo_name}: {card.primary_language or '?'}, {card.project_type or '?'}, entry={card.entrypoints[:3]}"
            for card in repo_cards
        )
        try:
            narrative = await gateway.complete(
                profile,
                [{"role": "user", "content": f"根据以下仓库信息，用中文用一段话概括整体技术路线。不得编造。\n\n{route_context}"}],
                max_tokens=512,
            )
            lines.insert(0, narrative.strip())
            lines.insert(1, "")
        except Exception as exc:
            logger.warning("technical_route LLM failed: %s", exc)

        claims.append(
            cf.make(
                f"技术路线分析涵盖 {len(repo_cards)} 个仓库",
                ClaimLabel.INFERENCE if section_eids else ClaimLabel.PENDING,
                section_eids,
            )
        )

        return (
            ReportSection(
                key="technical_route",
                title=self._title("technical_route", lang),
                markdown="\n".join(lines).strip(),
                claims=claims,
                evidence_ids=section_eids,
            ),
            [],
        )

    def _section_comparison_matrix(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        comparison: Any = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        # v2: 优先使用传入的 comparison，降级到 DB
        matrix = comparison or self.comparison_repo.get_by_task(task.task_id)
        if matrix is None:
            claim = cf.make("多仓库对比矩阵尚未生成", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="comparison_matrix",
                    title=self._title("comparison_matrix", lang),
                    markdown=self._format_claim_line(claim, digest=digest),
                    claims=[claim],
                    is_pending=True,
                ),
                ["对比矩阵尚未完成"],
            )

        lines: list[str] = []
        claims: list[ReportClaim] = []

        # v2: 结论优先
        top_repo = matrix.rankings[0] if matrix.rankings else None
        if top_repo:
            lines.append(f"**总体结论：** 在当前权重下，**{top_repo.repo_name}** 排名最高（加权总分 {top_repo.weighted_total:.2f}），")
            if matrix.limitations:
                lines.append(f"但此结论受 {len(matrix.limitations)} 项限制影响，需用户结合场景确认。")
            lines.append("")
        lines.append(f"**推荐：** {matrix.recommendation}")
        lines.append("")

        # v2: 排名
        lines.append("**排名：**")
        for i, rank in enumerate(matrix.rankings, 1):
            lines.append(f"{i}. {rank.repo_name} — 加权总分 **{rank.weighted_total:.2f}**")
        lines.append("")

        # v2: 关键差异
        lines.append("**关键差异：**")
        dim_zh = {
            "reproducibility": "复现性",
            "documentation": "文档完整度",
            "research_value": "研究价值",
            "engineering_fit": "工程契合度",
            "extensibility": "扩展性",
        }
        name_by_url = {r.repo_url: r.repo_name for r in matrix.rankings}
        for ds in matrix.scores:
            ds.rationale = self._clean_comparison_rationale(ds.rationale)
        seen_dims: set[str] = set()
        for ds in matrix.scores:
            dim = ds.dimension
            if dim in seen_dims:
                continue
            seen_dims.add(dim)
            short = name_by_url.get(ds.repo_url, ds.repo_url.rstrip("/").split("/")[-1][:20])
            label = dim_zh.get(dim, dim)
            lines.append(f"- **{label}：** {short} — {ds.rationale[:120]}")

        lines.append("")
        lines.append("**得分矩阵：**")
        lines.append("| 仓库 | 维度 | 分数 | 说明 |")
        lines.append("| --- | --- | --- | --- |")
        for ds in matrix.scores:
            short = name_by_url.get(ds.repo_url, ds.repo_url.rstrip("/").split("/")[-1][:20])
            lines.append(
                f"| {short} | {ds.dimension} | {ds.score:.2f} | {ds.rationale[:80]} |"
            )
            claims.append(
                cf.make(
                    f"{ds.repo_url}/{ds.dimension}: {ds.rationale[:120]}",
                    ds.label,
                    ds.evidence_ids,
                )
            )
        lines.append("")

        rec_claim = cf.make(
            matrix.recommendation,
            ClaimLabel.RECOMMENDATION if matrix.recommendation_evidence_ids else ClaimLabel.PENDING,
            matrix.recommendation_evidence_ids,
            requires_user_review=True,
        )
        claims.append(rec_claim)

        if matrix.limitations:
            lines.append("**局限：**")
            for lim in matrix.limitations[:8]:
                lim_claim = cf.make(lim, ClaimLabel.PENDING, [])
                claims.append(lim_claim)
                lines.append(self._format_claim_line(lim_claim, digest=digest))
            lines.append("")

        return (
            ReportSection(
                key="comparison_matrix",
                title=self._title("comparison_matrix", lang),
                markdown="\n".join(lines),
                claims=claims,
                evidence_ids=list(matrix.recommendation_evidence_ids),
            ),
            [],
        )

    def _section_reproducibility(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        reproducibility: Any = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        # v2: 如果有传入的 reproducibility 参数，优先使用
        repro = reproducibility or self.repro_repo.get_by_task(task.task_id)
        if repro is None or not repro.scores:
            claim = cf.make("复现性评估尚未执行", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="reproducibility",
                    title=self._title("reproducibility", lang),
                    markdown=self._format_claim_line(claim, digest=digest),
                    claims=[claim],
                    is_pending=True,
                ),
                ["复现性分析尚未完成"],
            )

        # 检查是否存在 run_log 证据
        has_run_log = any(e.source_type is SourceType.RUN_LOG for e in evidence_items)
        assessment_type = "static_reproducibility_assessment"
        if has_run_log:
            assessment_note = "> 评估类型：包含 run_log 实际运行检查。"
        else:
            assessment_note = (
                f"> 评估类型：**{STATIC_REPRO_ASSESSMENT_LABEL}**"
                "（无 run log，非实测复现。以下结论为静态推断，不可声称复现成功。）"
            )

        lines: list[str] = [assessment_note]
        claims: list[ReportClaim] = []
        section_eids: list[str] = []

        dim_labels = {
            "install_clarity": "安装清晰度",
            "dependency_risk": "依赖风险",
            "examples_availability": "示例可用度",
            "tests_availability": "测试可用度",
            "data_requirement_clarity": "数据需求清晰度",
            "hardware_requirement_clarity": "硬件需求清晰度",
            "external_service_dependency": "外部服务依赖",
            "documentation_quality": "文档质量",
        }

        for score in repro.scores:
            name = score.repo_name
            lines.append(f"\n### {name}")
            lines.append(f"**静态复现结论：** 综合得分 {score.overall_score:.2f}")
            lines.append("")

            # 维度得分（使用中文标签）
            lines.append("**各维度评估：**")
            for dim, val in score.dimension_scores.items():
                label = dim_labels.get(dim, dim)
                bar = "█" * int(val * 5) + "░" * (5 - int(val * 5))
                lines.append(f"- {label}: {val:.2f} {bar}")
            lines.append("")

            # 实践路径
            lines.append("**建议验证路径：**")
            if score.recommended_next_checks:
                for i, check in enumerate(score.recommended_next_checks[:5], 1):
                    lines.append(f"{i}. {check}")
            else:
                lines.append("1. 阅读 README 和安装文档")
                lines.append("2. 检查依赖是否可以安装")
                if any("install" in m.lower() for m in score.missing_info):
                    lines.append("3. ⚠️ 安装说明缺失或不完整，需先补充")
                lines.append("3. 尝试运行最小示例或测试")
                lines.append("4. 对照评估维度逐项验证")
            lines.append("")

            # 主要缺口
            if score.missing_info:
                lines.append("**主要缺口：**")
                for m in score.missing_info[:5]:
                    lines.append(f"- ⚠️ {m}")
                lines.append("")

            section_eids.extend(score.evidence_ids)
            summary_claim = cf.make(
                f"{name} 静态复现评估综合得分 {score.overall_score:.2f}",
                ClaimLabel.INFERENCE if score.evidence_ids else ClaimLabel.PENDING,
                score.evidence_ids,
            )
            claims.append(summary_claim)

        return (
            ReportSection(
                key="reproducibility",
                title=self._title("reproducibility", lang),
                markdown="\n".join(lines),
                claims=claims,
                evidence_ids=section_eids,
            ),
            [],
        )

    def _section_risks(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        lines: list[str] = []
        claims: list[ReportClaim] = []
        warnings: list[str] = []

        # v2: 按用户影响分组
        risk_groups: dict[str, list[str]] = {
            "阻塞型风险": [],
            "结果可信度风险": [],
            "工程集成风险": [],
            "维护/依赖风险": [],
            "证据不足风险": [],
        }

        # 计划未知项 → 阻塞型
        if plan and plan.unknowns:
            for u in plan.unknowns:
                risk_groups["阻塞型风险"].append(f"计划未知：{u}")

        # 仓库风险 → 工程集成 / 维护
        for card in repo_cards:
            for risk in card.risks:
                rl = risk.lower()
                if "dep" in rl or "依赖" in rl or "maintain" in rl or "archived" in rl:
                    risk_groups["维护/依赖风险"].append(f"{card.repo_name}: {risk}")
                elif "license" in rl or "兼容" in rl or "docker" in rl:
                    risk_groups["工程集成风险"].append(f"{card.repo_name}: {risk}")
                else:
                    risk_groups["结果可信度风险"].append(f"{card.repo_name}: {risk}")

        # 弱证据 → 证据不足
        weak = [e for e in evidence_items if e.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING)]
        if weak:
            for e in weak[:5]:
                ref = digest.by_id.get(e.id)
                label = ref.display_id if ref else e.id[:8]
                risk_groups["证据不足风险"].append(
                    f"{label}: {e.quote_or_summary[:120]} (strength={e.strength.value})"
                )

        for group, items in risk_groups.items():
            if not items:
                continue
            lines.append(f"### {group}")
            for item in items[:8]:
                label = ClaimLabel.PENDING if "证据不足" in group or "阻塞" in group else ClaimLabel.INFERENCE
                c = cf.make(item, label, [])
                claims.append(c)
                lines.append(self._format_claim_line(c, digest=digest))
            lines.append("")

        if not lines:
            lines.append("（暂无显著风险记录）")
            claims.append(cf.make("暂无显著风险记录", ClaimLabel.PENDING, []))

        if plan and plan.unknowns:
            warnings.append(f"计划中有 {len(plan.unknowns)} 项未知待澄清")
        if weak:
            warnings.append(f"有 {len(weak)} 条弱/缺失证据需关注")

        return (
            ReportSection(
                key="risks",
                title=self._title("risks", lang),
                markdown="\n".join(lines),
                claims=claims,
            ),
            warnings,
        )

    def _section_recommendation(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        comparison: Any = None,
        reproducibility: Any = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)
        matrix = comparison or self.comparison_repo.get_by_task(task.task_id)

        from ..models.comparison import ComparisonMatrix

        if isinstance(matrix, ComparisonMatrix) and matrix.rankings:
            top = matrix.rankings[0]
            top_name = top.repo_name
            eids = list(matrix.recommendation_evidence_ids)
        else:
            top = None
            top_name = "（暂无对比数据）"
            eids = []

        lines: list[str] = []
        claims: list[ReportClaim] = []
        is_pending = top is None

        scenarios = [
            (
                "快速 demo",
                f"建议优先尝试 **{top_name}**" if top else "暂无明确推荐",
                f"文档与入口最清晰，适合快速了解。{'需检查安装步骤是否可直接运行。' if top else ''}" if top else "需生成对比矩阵后再评估。",
            ),
            (
                "论文复现",
                f"{'建议从 ' + top_name + ' 开始，' if top else ''}需核实论文关系与安装完整性。",
                "优先确认论文与仓库版本对应关系、安装说明和数据要求。"
            ),
            (
                "工程集成",
                f"{'关注 ' + top_name + ' 的' if top else '需评估'}依赖复杂度、License 兼容性和模块化程度。",
                "重点检查生产环境依赖、配置灵活度和 API 稳定性。"
            ),
            (
                "二次开发",
                f"{'评估 ' + top_name + ' 的' if top else '需评估'}架构扩展性、代码可读性和社区支持。",
                "优先检查核心模块边界、测试覆盖率和贡献指南。"
            ),
        ]

        for scenario, rec, rationale in scenarios:
            lines.append(f"### {scenario}")
            lines.append(f"**建议：** {rec}")
            lines.append(f"**理由：** {rationale}")
            lines.append("")
            claims.append(
                cf.make(
                    f"{scenario}：{rec}",
                    ClaimLabel.RECOMMENDATION if eids else ClaimLabel.PENDING,
                    eids,
                    requires_user_review=True,
                )
            )

        lines.append("> 以上建议属于 **recommendation**，需要用户结合实际资源确认，不构成未经审批的最终强推荐。")
        lines.append("")

        warnings = []
        if is_pending:
            warnings.append("推荐与场景尚未完成，需用户审阅（R-004）")

        return (
            ReportSection(
                key="recommendation",
                title=self._title("recommendation", lang),
                markdown="\n".join(lines),
                claims=claims,
                is_pending=is_pending,
                evidence_ids=eids,
            ),
            warnings,
        )

    def _section_next_steps(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        reproducibility: Any = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        # v2: 可执行行动清单，不再只是 plan pending steps
        steps: list[str] = []

        # 1. 从复现评估获取推荐下一步
        repro = reproducibility or self.repro_repo.get_by_task(task.task_id)
        if repro and repro.scores:
            for score in repro.scores:
                for check in score.recommended_next_checks[:3]:
                    steps.append(f"验证 {score.repo_name}：{check}")
                for m in score.missing_info[:2]:
                    steps.append(f"补充 {score.repo_name} 缺失信息：{m}")

        # 2. 检查示例和入口
        for card in repo_cards:
            if card.entrypoints:
                steps.append(f"尝试运行 {card.repo_name} 的入口文件：{card.entrypoints[0]}")
            if card.test_commands:
                steps.append(f"运行 {card.repo_name} 的测试：{card.test_commands[0]}")

        # 3. 从 plan unknowns 添加待确认项
        if plan and plan.unknowns:
            for u in plan.unknowns[:3]:
                steps.append(f"澄清：{u}")

        # 4. 弱证据补充
        weak = [e for e in evidence_items if e.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING)]
        if weak:
            steps.append(f"补充 {len(weak)} 条弱/缺失证据的验证")

        # 5. 最终选型
        steps.append("若要最终选型，请确认对比权重并结合实际场景审批最终推荐")

        if not steps:
            steps.append("所有步骤已完成，可导出报告确认。")

        lines: list[str] = []
        claims: list[ReportClaim] = []
        for i, step in enumerate(steps[:12], 1):
            lines.append(f"{i}. {step}")
            claims.append(
                cf.make(step, ClaimLabel.RECOMMENDATION, [], requires_user_review=True)
            )

        return (
            ReportSection(
                key="next_steps",
                title=self._title("next_steps", lang),
                markdown="\n".join(lines),
                claims=claims,
            ),
            [],
        )

    def _section_evidence_references(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
        evidence_digest: EvidenceDigest | None = None,
        claim_factory: ClaimFactory | None = None,
        **__: Any,
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        digest = evidence_digest or build_evidence_digest(evidence_items)
        cf = claim_factory or ClaimFactory(digest)

        if not evidence_items:
            claim = cf.make("尚无证据条目", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="evidence_references",
                    title=self._title("evidence_references", lang),
                    markdown=self._format_claim_line(claim, digest=digest),
                    claims=[claim],
                    is_pending=True,
                    evidence_ids=[],
                ),
                ["证据链为空"],
            )

        lines: list[str] = [
            "本节保留可追溯证据。正文中使用 E01/E02 等短编号；完整 evidence id 和 source_uri 在此列出。\n"
        ]
        claims: list[ReportClaim] = []
        section_evidence_ids: list[str] = []

        # v2: 按 source_type 分组
        group_titles = {
            "repo_file": "### 仓库文件证据",
            "paper": "### 论文 / 文档",
            "web": "### 网络资料",
            "run_log": "### 运行日志",
            "user_confirmation": "### 用户确认",
            "model_inference": "### 模型推断",
        }
        for stype, title in group_titles.items():
            refs = digest.by_source_type.get(stype, [])
            if not refs:
                continue
            lines.append(title)
            lines.append("")
            for ref in refs:
                strength_mark = ""
                if ref.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING):
                    strength_mark = " ⚠️弱/缺失证据"
                locator_text = f" @ {ref.locator}" if ref.locator else ""
                item = next(
                    (e for e in evidence_items if e.id == ref.evidence_id), None
                )
                label = self._evidence_to_label(item) if item else ClaimLabel.INFERENCE
                summary = self._clean_reference_summary(ref.summary)
                lines.append(
                    f"- **{ref.display_id}** [{label.value}] "
                    f"`{ref.source_type.value}` {ref.source_uri}{locator_text}{strength_mark}\n"
                    f"  原始 ID：`{ref.evidence_id}`\n"
                    f"  摘要：{summary}\n"
                )
                claims.append(
                    cf.make(summary, label, [ref.evidence_id])
                )
                section_evidence_ids.append(ref.evidence_id)

        return (
            ReportSection(
                key="evidence_references",
                title=self._title("evidence_references", lang),
                markdown="\n".join(lines),
                claims=claims,
                evidence_ids=section_evidence_ids,
            ),
            [],
        )
