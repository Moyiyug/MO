"""报告生成服务（PRD F-011）。"""

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
from ..models.report import REPORT_SECTION_KEYS, REPORT_SECTION_TITLES, Report, ReportSection
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
        plan = self.plan_repo.get_latest_by_task(task_id)
        events = self.event_repo.list_since(task_id, 0)
        repo_cards = self.repo_card_repo.list_by_task(task_id)
        evidence_items = self.evidence_repo.list_by_task(task_id)
        code_insights = self._derive_code_insights(evidence_items)

        pending_warnings: list[str] = []
        sections: list[ReportSection] = []

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
            section, warnings = builder(
                task=task,
                plan=plan,
                events=events,
                repo_cards=repo_cards,
                evidence_items=evidence_items,
            )
            section_map[key] = section
            pending_warnings.extend(warnings)

        exec_section, exec_warnings = await self._section_execution_summary(
            task=task,
            events=events,
            evidence_items=evidence_items,
        )
        section_map["execution_summary"] = exec_section
        pending_warnings.extend(exec_warnings)

        tech_section, tech_warnings = await self._section_technical_route(
            task=task,
            repo_cards=repo_cards,
            evidence_items=evidence_items,
            code_insights=code_insights,
        )
        section_map["technical_route"] = tech_section
        pending_warnings.extend(tech_warnings)

        for key in REPORT_SECTION_KEYS:
            sections.append(section_map[key])

        markdown = self._assemble_markdown(sections)
        report = Report(
            id=uuid.uuid4().hex,
            task_id=task_id,
            sections=sections,
            pending_warnings=list(dict.fromkeys(pending_warnings)),
            generated_at=datetime.now(timezone.utc),
            markdown=markdown,
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

    def _format_claim_line(self, claim: ReportClaim) -> str:
        eid_part = ""
        if claim.evidence_ids:
            eid_part = f" (evidence: {', '.join(claim.evidence_ids)})"
        return f"- [{claim.label.value}] {claim.claim}{eid_part}"

    def _assemble_markdown(self, sections: list[ReportSection]) -> str:
        parts: list[str] = []
        for section in sections:
            parts.append(f"## {section.title}\n")
            if section.is_pending:
                parts.append("> **[pending]** 本节数据尚未完备。\n")
            parts.append(section.markdown.strip())
            parts.append("")
        return "\n".join(parts).strip() + "\n"

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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        lines = [
            f"**目标：** {task.goal}",
            f"**仓库：** {', '.join(task.repo_urls) or '（无）'}",
            f"**论文链接：** {', '.join(task.paper_urls) or '（无）'}",
        ]
        if task.template:
            lines.append(f"**模板：** {task.template}")

        # 用户输入的目标是确定性事实（来源 TaskTable）
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
        claims = [
            self._make_claim(
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        boundaries = list(plan.confirmed_context) if plan else []
        if not boundaries:
            md = "（暂无用户确认边界）"
            claims = [
                self._make_claim("用户确认边界尚未记录", ClaimLabel.PENDING, [])
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
        lines: list[str] = []
        claims = []
        for b in boundaries:
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
            claim = self._make_claim(b, ClaimLabel.FACT, [ev.id])
            claims.append(claim)
            lines.append(self._format_claim_line(claim))
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        if plan is None:
            return (
                ReportSection(
                    key="approved_plan",
                    title=self._title("approved_plan", lang),
                    markdown="（计划尚未生成）",
                    claims=[self._make_claim("计划尚未生成", ClaimLabel.PENDING, [])],
                    is_pending=True,
                ),
                ["已批准计划缺失"],
            )
        lines = [f"**摘要：** {plan.task_summary}", "", "**步骤：**"]
        claims: list[ReportClaim] = []
        for step in plan.proposed_steps:
            line = f"- {step.title} (`{step.tool.value}`, risk={step.risk_level.value})"
            lines.append(line)
            claims.append(
                self._make_claim(
                    f"计划步骤：{step.title}",
                    ClaimLabel.PENDING,
                    [],
                )
            )
        return (
            ReportSection(
                key="approved_plan",
                title=self._title("approved_plan", lang),
                markdown="\n".join(lines),
                claims=claims,
            ),
            [],
        )

    async def _section_execution_summary(
        self,
        *,
        task: TaskResponse,
        events: list[NodeEvent],
        evidence_items: list[EvidenceItem],
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        event_lines = []
        evidence_ids: list[str] = []
        for ev in events:
            status_val = ev.status.value if isinstance(ev.status, NodeStatus) else ev.status
            event_lines.append(f"- `{ev.node}`: {status_val}")
            evidence_ids.extend(ev.evidence_ids or [])

        event_text = "\n".join(event_lines) or "（无执行事件）"
        gateway = self._ensure_gateway()
        profile = gateway.select(need_reasoning=True, long_context=True)
        if lang == "en":
            prompt = (
                "Write a concise execution summary paragraph based ONLY on the node events below. "
                "Do not invent facts.\n\n"
                f"Events:\n{event_text}"
            )
        else:
            prompt = (
                "根据以下节点执行事件，用中文写一段简洁的执行摘要。"
                "只能基于给定事件，不得编造。\n\n"
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
            narrative = "（执行摘要生成失败——将在下方展示原始节点事件）"
        claims = [
            self._make_claim(
                narrative.strip(),
                ClaimLabel.INFERENCE if narrative else ClaimLabel.PENDING,
                list(dict.fromkeys(evidence_ids)) if narrative else [],
            )
        ]
        md = narrative.strip() + "\n\n**节点事件：**\n" + event_text
        return (
            ReportSection(
                key="execution_summary",
                title=self._title("execution_summary", lang),
                markdown=md,
                claims=claims,
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        if not repo_cards:
            return (
                ReportSection(
                    key="repo_overview",
                    title=self._title("repo_overview", lang),
                    markdown="（尚未摄取仓库）",
                    claims=[
                        self._make_claim("仓库概览尚未生成", ClaimLabel.PENDING, [])
                    ],
                    is_pending=True,
                ),
                ["仓库概览数据缺失"],
            )
        lines: list[str] = []
        claims: list[ReportClaim] = []
        evidence_by_id = {e.id: e for e in evidence_items}
        for card in repo_cards:
            lines.append(f"### {card.repo_name or card.repo_url}")
            lines.append(f"- **语言：** {card.primary_language or 'unknown'}")
            lines.append(f"- **类型：** {card.project_type or 'unknown'}")
            lines.append(f"- **入口：** {', '.join(card.entrypoints) or 'unknown'}")
            if card.summary:
                lines.append(f"\n{card.summary[:500]}")
            for eid in card.evidence_ids[:3]:
                ev = evidence_by_id.get(eid)
                if ev:
                    label = self._evidence_to_label(ev)
                    claim = self._make_claim(ev.quote_or_summary[:200], label, [eid])
                    claims.append(claim)
                    lines.append(self._format_claim_line(claim))
            lines.append("")
        return (
            ReportSection(
                key="repo_overview",
                title=self._title("repo_overview", lang),
                markdown="\n".join(lines).strip(),
                claims=claims,
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        research_evidence = [
            e
            for e in evidence_items
            if e.source_type in (SourceType.PAPER, SourceType.WEB)
            or e.material_type is not None
        ]
        if not research_evidence:
            claim = self._make_claim(
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
        code_insights: list[dict[str, Any]],
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        insight_lines = []
        evidence_ids: list[str] = []
        for ins in code_insights:
            if ins.get("type") == "core_module":
                insight_lines.append(f"- 核心模块: {ins.get('module')}")
            elif ins.get("type") == "execution_path":
                insight_lines.append(f"- 执行路径: {ins.get('path')}")
            eid = ins.get("evidence_id")
            if eid:
                evidence_ids.append(eid)

        if not insight_lines:
            claim = self._make_claim("技术路线分析数据不足", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="technical_route",
                    title=self._title("technical_route", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                ["技术路线分析证据不足"],
            )

        context = "\n".join(insight_lines)
        gateway = self._ensure_gateway()
        profile = gateway.select(need_reasoning=True, long_context=True)
        if lang == "en":
            prompt = (
                "Analyze the technical route based ONLY on the code insights below. "
                "Respond in one concise paragraph.\n\n"
                f"Insights:\n{context}"
            )
        else:
            prompt = (
                "根据以下代码理解结果，用中文分析技术路线。"
                "只能基于给定信息，不得编造。\n\n"
                f"洞察：\n{context}"
            )
        narrative = ""
        try:
            narrative = await gateway.complete(
                profile,
                [{"role": "user", "content": prompt}],
                max_tokens=512,
            )
        except Exception as exc:
            logger.warning("technical_route LLM failed: %s", exc)
            narrative = "（技术路线分析生成失败——将在下方展示原始代码洞察）"
        claims = [
            self._make_claim(
                narrative.strip(),
                ClaimLabel.INFERENCE if narrative else ClaimLabel.PENDING,
                list(dict.fromkeys(evidence_ids)) if narrative else [],
            )
        ]
        md = narrative.strip() + "\n\n**代码洞察：**\n" + context
        return (
            ReportSection(
                key="technical_route",
                title=self._title("technical_route", lang),
                markdown=md,
                claims=claims,
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        matrix = self.comparison_repo.get_by_task(task.task_id)
        if matrix is None:
            claim = self._make_claim(
                "多仓库对比矩阵尚未生成",
                ClaimLabel.PENDING,
                [],
            )
            return (
                ReportSection(
                    key="comparison_matrix",
                    title=self._title("comparison_matrix", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                ["对比矩阵尚未完成"],
            )

        lines: list[str] = []
        claims: list[ReportClaim] = []

        lines.append("**排名：**")
        for i, rank in enumerate(matrix.rankings, 1):
            lines.append(
                f"{i}. {rank.repo_name} — 加权总分 **{rank.weighted_total:.2f}**"
            )

        lines.append("\n**维度得分：**")
        lines.append("| 仓库 | 维度 | 分数 | 说明 |")
        lines.append("| --- | --- | --- | --- |")
        # 用 rankings 中的 repo_name 替代 URL 解析（更可靠）
        name_by_url = {r.repo_url: r.repo_name for r in matrix.rankings}
        for ds in matrix.scores:
            short = name_by_url.get(ds.repo_url, ds.repo_url.rstrip("/").split("/")[-1][:20])
            lines.append(
                f"| {short} | {ds.dimension} | {ds.score:.2f} | {ds.rationale[:80]} |"
            )
            claims.append(
                self._make_claim(
                    f"{ds.repo_url} / {ds.dimension}: {ds.rationale[:120]}",
                    ds.label,
                    ds.evidence_ids,
                )
            )

        lines.append(f"\n**推荐：** {matrix.recommendation}")
        rec_claim = self._make_claim(
            matrix.recommendation,
            ClaimLabel.INFERENCE if matrix.recommendation_evidence_ids else ClaimLabel.PENDING,
            matrix.recommendation_evidence_ids,
        )
        claims.append(rec_claim)
        lines.append(self._format_claim_line(rec_claim))

        if matrix.limitations:
            lines.append("\n**局限：**")
            for lim in matrix.limitations:
                lim_claim = self._make_claim(lim, ClaimLabel.PENDING, [])
                claims.append(lim_claim)
                lines.append(self._format_claim_line(lim_claim))

        return (
            ReportSection(
                key="comparison_matrix",
                title=self._title("comparison_matrix", lang),
                markdown="\n".join(lines),
                claims=claims,
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        report = self.repro_repo.get_by_task(task.task_id)
        if report is None or not report.scores:
            claim = self._make_claim(
                "复现性评估尚未执行",
                ClaimLabel.PENDING,
                [],
            )
            return (
                ReportSection(
                    key="reproducibility",
                    title=self._title("reproducibility", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                ["复现性分析尚未完成"],
            )

        lines: list[str] = [
            f"> 评估类型：**{STATIC_REPRO_ASSESSMENT_LABEL}**（无 run log，非实测复现）"
        ]
        claims: list[ReportClaim] = []

        for score in report.scores:
            lines.append(f"\n### {score.repo_name}")
            lines.append(f"- **综合得分：** {score.overall_score:.2f}")
            lines.append("- **维度得分：**")
            for dim, val in score.dimension_scores.items():
                lines.append(f"  - {dim}: {val:.2f}")
            if score.missing_info:
                lines.append("- **缺失信息：**")
                for m in score.missing_info:
                    lines.append(f"  - {m}")
            if score.recommended_next_checks:
                lines.append("- **建议下一步：**")
                for n in score.recommended_next_checks:
                    lines.append(f"  - {n}")
            summary_claim = self._make_claim(
                f"{score.repo_name} 静态复现评估综合得分 {score.overall_score:.2f}",
                ClaimLabel.INFERENCE if score.evidence_ids else ClaimLabel.PENDING,
                score.evidence_ids,
            )
            claims.append(summary_claim)
            lines.append(self._format_claim_line(summary_claim))

        return (
            ReportSection(
                key="reproducibility",
                title=self._title("reproducibility", lang),
                markdown="\n".join(lines),
                claims=claims,
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        lines: list[str] = []
        claims: list[ReportClaim] = []
        warnings: list[str] = []

        if plan and plan.unknowns:
            lines.append("**计划未知项：**")
            for u in plan.unknowns:
                c = self._make_claim(u, ClaimLabel.PENDING, [])
                claims.append(c)
                lines.append(self._format_claim_line(c))

        for card in repo_cards:
            for risk in card.risks:
                eids = card.evidence_ids[:1]
                label = ClaimLabel.INFERENCE if eids else ClaimLabel.PENDING
                c = self._make_claim(f"{card.repo_name}: {risk}", label, eids)
                claims.append(c)
                lines.append(self._format_claim_line(c))

        weak = [e for e in evidence_items if e.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING)]
        if weak:
            lines.append("\n**弱证据：**")
            for e in weak[:5]:
                c = self._make_claim(e.quote_or_summary[:150], ClaimLabel.PENDING, [e.id])
                claims.append(c)
                lines.append(self._format_claim_line(c))

        if not lines:
            lines.append("（暂无显著风险记录）")
            claims.append(self._make_claim("暂无显著风险记录", ClaimLabel.PENDING, []))

        if plan and plan.unknowns:
            warnings.append(f"计划中有 {len(plan.unknowns)} 项未知待澄清")

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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        pending_claim = self._make_claim(
            "推荐与场景分析尚未完成，需用户审阅后确认",
            ClaimLabel.PENDING,
            [],
        )
        return (
            ReportSection(
                key="recommendation",
                title=self._title("recommendation", lang),
                markdown="\n".join(
                    [
                        self._format_claim_line(pending_claim),
                        "> **[recommendation]** 本节为待定推荐，不构成最终强推荐。",
                    ]
                ),
                claims=[pending_claim],
                is_pending=True,
            ),
            ["推荐与场景尚未完成，需用户审阅（R-004）"],
        )

    def _section_next_steps(
        self,
        *,
        task: TaskResponse,
        plan: Plan | None,
        events: list[NodeEvent],
        repo_cards: list,
        evidence_items: list[EvidenceItem],
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        if not plan or not plan.proposed_steps:
            claim = self._make_claim("后续步骤尚未定义", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="next_steps",
                    title=self._title("next_steps", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                [],
            )
        pending_steps = [s for s in plan.proposed_steps if s.status.value == "pending"]
        lines = []
        claims = []
        for step in pending_steps[:10]:
            c = self._make_claim(f"待执行：{step.title}", ClaimLabel.PENDING, [])
            claims.append(c)
            lines.append(self._format_claim_line(c))
        return (
            ReportSection(
                key="next_steps",
                title=self._title("next_steps", lang),
                markdown="\n".join(lines) or "（无待执行步骤）",
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
    ) -> tuple[ReportSection, list[str]]:
        lang = task.output_language.value
        if not evidence_items:
            claim = self._make_claim("尚无证据条目", ClaimLabel.PENDING, [])
            return (
                ReportSection(
                    key="evidence_references",
                    title=self._title("evidence_references", lang),
                    markdown=self._format_claim_line(claim),
                    claims=[claim],
                    is_pending=True,
                ),
                ["证据链为空"],
            )
        lines: list[str] = []
        claims: list[ReportClaim] = []
        for item in evidence_items:
            label = self._evidence_to_label(item)
            locator = f" @ {item.locator}" if item.locator else ""
            summary = item.quote_or_summary[:300].replace("\n", " ")
            line = (
                f"### evidence-{item.id}\n"
                f"- **[{item.id}]** [{label.value}] "
                f"`{item.source_type.value}` {item.source_uri}{locator}: {summary}"
            )
            lines.append(line)
            claims.append(
                self._make_claim(summary, label, [item.id])
            )
        return (
            ReportSection(
                key="evidence_references",
                title=self._title("evidence_references", lang),
                markdown="\n".join(lines),
                claims=claims,
            ),
            [],
        )
