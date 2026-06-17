"""plan_builder 节点：规则 mock 生成结构化 Plan（不接真实模型）。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ...models.enums import PlanStepStatus, PlanStepTool, RiskLevel
from ...models.plan import (
    DEFAULT_RUBRIC_WEIGHTS,
    ClarifyingQuestion,
    Plan,
    PlanStep,
    ReportRubric,
)
from ...models.repo_discovery import RepoCandidate
from ..state import MOState


def _step(
    step_id: str,
    node_id: str,
    title: str,
    description: str,
    tool: PlanStepTool,
    risk_level: RiskLevel,
    requires_approval: bool,
    expected_outputs: list[str],
    depends_on: list[str],
) -> PlanStep:
    return PlanStep(
        id=step_id,
        node_id=node_id,
        title=title,
        description=description,
        tool=tool,
        risk_level=risk_level,
        requires_approval=requires_approval,
        expected_outputs=expected_outputs,
        depends_on=depends_on,
        user_editable=True,
        status=PlanStepStatus.PENDING,
    )


def build_plan_from_state(state: MOState) -> Plan:
    """从图状态构建 Plan（纯函数，供节点与单测调用）。"""
    task_id = state["task_id"]
    goal = state.get("goal", "")
    repo_urls = list(state.get("repo_urls") or [])
    paper_urls = list(state.get("paper_urls") or [])
    output_language = state.get("output_language", "zh")
    permissions = dict(state.get("permissions") or {})
    answers = dict(state.get("clarification_answers") or {})

    candidates = [
        RepoCandidate.model_validate(c) for c in (state.get("repo_candidates") or [])
    ]
    selected = [c for c in candidates if c.selected]
    # 计划步骤数量依据：已选 > 全部候选 > 用户直接提供的 repo_urls
    effective = selected or candidates
    repo_count = len(effective) if effective else len(repo_urls)

    allow_clone = bool(permissions.get("allow_repo_clone", True))
    allow_web = bool(permissions.get("allow_web_search", False))
    allow_smoke = bool(permissions.get("allow_smoke_test", False))

    if candidates and not selected:
        task_summary = f"{goal}（已发现 {len(candidates)} 个候选仓库，待选择调研对象）"
    else:
        task_summary = f"{goal}（调研 {repo_count} 个仓库）"

    confirmed_context = [
        f"研究目标: {goal}",
        f"待调研仓库数量: {repo_count}",
        f"输出语言: {output_language}",
        f"允许克隆仓库: {allow_clone}",
        f"允许联网调研: {allow_web}",
    ]
    if candidates:
        confirmed_context.append(f"自动发现候选仓库: {len(candidates)} 个")
    if effective:
        confirmed_context.append(
            "仓库列表: " + ", ".join(c.repo_name for c in effective[:10])
        )
    elif repo_urls:
        confirmed_context.append("仓库列表: " + ", ".join(repo_urls))

    unknowns: list[str] = []
    clarifying_questions: list[dict] = []

    if candidates and not selected:
        unknowns.append(
            f"已自动发现 {len(candidates)} 个候选仓库，请在计划审阅页勾选 1-5 个作为调研对象"
        )
    if not candidates and not repo_urls:
        unknowns.append("未发现候选仓库且未提供仓库 URL，请补充仓库或调整研究目标")

    if repo_count > 1 and "comparison_focus" not in answers:
        clarifying_questions.append(
            {
                "id": "comparison_focus",
                "question": "多个仓库的对比重点是什么？（如可复现性、工程成熟度、研究价值）",
                "options": ["可复现性", "工程成熟度", "研究价值", "综合对比"],
                "answer": answers.get("comparison_focus"),
                "required": True,
            }
        )

    if not paper_urls:
        unknowns.append("未提供论文/文档链接，论文关系可能无法完全确认")

    if answers.get("comparison_focus"):
        confirmed_context.append(f"对比重点: {answers['comparison_focus']}")

    steps: list[PlanStep] = []
    prev_id: str | None = None

    def add(step_id: str, node_id: str, **kwargs) -> None:
        nonlocal prev_id
        depends = [prev_id] if prev_id else []
        steps.append(_step(step_id, node_id, depends_on=depends, **kwargs))
        prev_id = step_id

    add(
        "step_repo_ingest",
        node_id="repo_ingest",
        title="仓库调研",
        description="对选定的候选仓库使用 gitingest 提取 README、依赖、目录结构与关键文件摘要",
        tool=PlanStepTool.REPO_INGEST,
        risk_level=RiskLevel.MEDIUM if not allow_clone else RiskLevel.LOW,
        requires_approval=not allow_clone,
        expected_outputs=["RepoCard", "file_tree_summary"],
    )
    add(
        "step_code_understanding",
        node_id="code_understanding",
        title="代码理解",
        description="识别核心模块、安装路径、运行入口与测试命令",
        tool=PlanStepTool.CODE_UNDERSTANDING,
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        expected_outputs=["entrypoints", "module_map"],
    )
    add(
        "step_paper_research",
        node_id="paper_research",
        title="论文与资料补充",
        description="基于用户提供的论文链接与 README 关联资料进行补充调研",
        tool=PlanStepTool.PAPER_RESEARCH,
        risk_level=RiskLevel.HIGH if not allow_web else RiskLevel.MEDIUM,
        requires_approval=not allow_web,
        expected_outputs=["paper_context", "material_classification"],
    )
    add(
        "step_repro_eval",
        node_id="reproducibility",
        title="复现评估",
        description="评估安装清晰度、依赖风险、示例与文档质量（静态评估）",
        tool=PlanStepTool.REPRO_EVAL,
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        expected_outputs=["ReproducibilityScore"],
    )

    if repo_count > 1:
        add(
            "step_comparison",
            node_id="comparison_builder",
            title="多仓库对比",
            description="按默认权重生成对比矩阵与场景化推荐",
            tool=PlanStepTool.COMPARISON,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            expected_outputs=["comparison_matrix"],
        )

    if allow_smoke:
        add(
            "step_sandbox",
            node_id="sandbox_runner",
            title="冒烟测试（可选）",
            description="在审批后于沙箱中执行白名单命令进行 smoke test",
            tool=PlanStepTool.SANDBOX_RUNNER,
            risk_level=RiskLevel.HIGH,
            requires_approval=True,
            expected_outputs=["run_log"],
        )

    add(
        "step_report",
        node_id="report_writer",
        title="报告生成",
        description="生成带 fact/inference/recommendation/pending 标签的结构化报告",
        tool=PlanStepTool.REPORT_WRITER,
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        expected_outputs=["markdown_report"],
    )

    risk_summary = [
        f"步骤「{s.title}」需要用户审批" for s in steps if s.requires_approval
    ]
    if not risk_summary:
        risk_summary.append("本计划无高风险步骤，但仍需用户批准后方可执行")

    return Plan(
        id=uuid.uuid4().hex,
        task_id=task_id,
        task_summary=task_summary,
        confirmed_context=confirmed_context,
        unknowns=unknowns,
        clarifying_questions=[ClarifyingQuestion.model_validate(q) for q in clarifying_questions],
        proposed_steps=steps,
        report_rubric=ReportRubric(weights=dict(DEFAULT_RUBRIC_WEIGHTS)),
        risk_summary=risk_summary,
        approval_required=True,
        repo_candidates=candidates,
        created_at=datetime.now(timezone.utc),
    )


def plan_builder(state: MOState) -> MOState:
    plan = build_plan_from_state(state)
    return {"plan": plan.model_dump(mode="json")}
