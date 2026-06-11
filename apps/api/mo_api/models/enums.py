"""跨里程碑共用枚举。

这些枚举是前后端的真相源；前端 apps/web/src/types 必须与此保持一致。
对应 PRD §4（任务状态机）、F-009（证据）、F-010（节点状态）、F-002（风险等级）。
"""

from __future__ import annotations

from enum import Enum


class TaskStatus(str, Enum):
    """任务状态（PRD §4）。"""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_USER_CLARIFICATION = "WAITING_USER_CLARIFICATION"
    WAITING_USER_APPROVAL = "WAITING_USER_APPROVAL"
    PLAN_APPROVED = "PLAN_APPROVED"
    EXECUTING = "EXECUTING"
    REPLANNING = "REPLANNING"
    REPORT_DRAFT = "REPORT_DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DONE = "DONE"
    FAILED = "FAILED"


class OutputLanguage(str, Enum):
    """报告输出语言。"""

    ZH = "zh"
    EN = "en"


class NodeStatus(str, Enum):
    """工作流节点状态（PRD F-010）。后续里程碑使用。"""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ClaimLabel(str, Enum):
    """报告论断标签（PRD F-009 / R-003）。后续里程碑使用。"""

    FACT = "fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    PENDING = "pending"


class EvidenceStrength(str, Enum):
    """证据强度（PRD F-009）。后续里程碑使用。"""

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
    MISSING = "missing"


class SourceType(str, Enum):
    """证据来源类型（PRD F-009）。后续里程碑使用。"""

    REPO_FILE = "repo_file"
    PAPER = "paper"
    WEB = "web"
    RUN_LOG = "run_log"
    USER_CONFIRMATION = "user_confirmation"
    MODEL_INFERENCE = "model_inference"


class RiskLevel(str, Enum):
    """计划步骤风险等级（PRD F-002）。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanStepTool(str, Enum):
    """计划步骤工具类型（PRD F-002）。"""

    REPO_INGEST = "repo_ingest"
    CODE_UNDERSTANDING = "code_understanding"
    PAPER_RESEARCH = "paper_research"
    REPRO_EVAL = "repro_eval"
    COMPARISON = "comparison"
    CRITIC_REVIEW = "critic_review"
    REPORT_WRITER = "report_writer"
    SANDBOX_RUNNER = "sandbox_runner"


class PlanStepStatus(str, Enum):
    """计划步骤状态（PRD F-002）。"""

    PENDING = "pending"
    APPROVED = "approved"
    SKIPPED = "skipped"


# ---- code_understanding ↔ report_service 共享常量 ----
# code_understanding 节点写入 evidence 时使用这些 locator / 前缀；
# report_service._derive_code_insights 据此匹配。修改时两边必须同步。

CODE_INSIGHT_LOCATOR_EXECUTION_PATH = "code:execution_path"
CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX = "code:core_module:"
CODE_INSIGHT_LOCATOR_REPO_SUMMARY = "code:repo_summary"
CODE_INSIGHT_PREFIX_CORE_MODULE = "Core module:"


class MaterialType(str, Enum):
    """论文/资料分类（PRD F-006）。"""

    OFFICIAL_REPO_PAPER = "official_repo_paper"
    OFFICIAL_DOC = "official_doc"
    BACKGROUND_REFERENCE = "background_reference"
    MODEL_SUGGESTED_REFERENCE = "model_suggested_reference"
    UNVERIFIED_REFERENCE = "unverified_reference"


# PRD F-007 复现评估维度
REPRO_DIMENSIONS: list[str] = [
    "install_clarity",
    "dependency_risk",
    "examples_availability",
    "tests_availability",
    "data_requirement_clarity",
    "hardware_requirement_clarity",
    "external_service_dependency",
    "documentation_quality",
]

STATIC_REPRO_ASSESSMENT_LABEL = "static_reproducibility_assessment"
