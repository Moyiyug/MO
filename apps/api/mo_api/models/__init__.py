"""Pydantic 数据模型（API + 领域 + 枚举）。"""

from .comparison import (
    COMPARISON_DIMENSIONS,
    ComparisonMatrix,
    DimensionScore,
    RecomputeComparisonRequest,
    RepoRanking,
    WEIGHTED_DIMENSIONS,
)
from .enums import (
    CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX,
    CODE_INSIGHT_LOCATOR_EXECUTION_PATH,
    CODE_INSIGHT_LOCATOR_REPO_SUMMARY,
    CODE_INSIGHT_PREFIX_CORE_MODULE,
    REPRO_DIMENSIONS,
    STATIC_REPRO_ASSESSMENT_LABEL,
    ClaimLabel,
    EvidenceStrength,
    MaterialType,
    NodeStatus,
    OutputLanguage,
    PlanStepStatus,
    PlanStepTool,
    RiskLevel,
    SourceType,
    TaskStatus,
)
from .events import (
    ExecuteResponse,
    NodeEvent,
    StepApproveRequest,
    StepApproveResponse,
)
from .evidence import EvidenceItem, ReportClaim
from .model import (
    ModelCapabilitiesResponse,
    ModelCapability,
    ModelProfile,
    ModelProfilePublic,
    ModelProfilesConfig,
    ModelTestRequest,
    ModelTestResponse,
)
from .plan import (
    DEFAULT_RUBRIC_WEIGHTS,
    ApprovePlanRequest,
    ApprovePlanResponse,
    ClarificationAnswer,
    ClarificationsRequest,
    ClarifyingQuestion,
    Plan,
    PlanResponse,
    PlanStep,
    ReplanRequest,
    ReportRubric,
)
from .report import REPORT_SECTION_KEYS, REPORT_SECTION_TITLES, Report, ReportSection
from .repo import RepoCard, RepoDigest
from .reproducibility import PaperMaterial, ReproducibilityReport, ReproducibilityScore
from .task import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskPermissions,
    TaskResponse,
)
from .validators import RepoUrlError

__all__ = [
    # comparison
    "COMPARISON_DIMENSIONS",
    "ComparisonMatrix",
    "DimensionScore",
    "RecomputeComparisonRequest",
    "RepoRanking",
    "WEIGHTED_DIMENSIONS",
    # enums
    "CODE_INSIGHT_LOCATOR_CORE_MODULE_PREFIX",
    "CODE_INSIGHT_LOCATOR_EXECUTION_PATH",
    "CODE_INSIGHT_LOCATOR_REPO_SUMMARY",
    "CODE_INSIGHT_PREFIX_CORE_MODULE",
    "REPRO_DIMENSIONS",
    "STATIC_REPRO_ASSESSMENT_LABEL",
    "ClaimLabel",
    "EvidenceStrength",
    "MaterialType",
    "NodeStatus",
    "OutputLanguage",
    "PlanStepStatus",
    "PlanStepTool",
    "RiskLevel",
    "SourceType",
    "TaskStatus",
    # events
    "ExecuteResponse",
    "NodeEvent",
    "StepApproveRequest",
    "StepApproveResponse",
    # evidence
    "EvidenceItem",
    "ReportClaim",
    # model
    "ModelCapabilitiesResponse",
    "ModelCapability",
    "ModelProfile",
    "ModelProfilePublic",
    "ModelProfilesConfig",
    "ModelTestRequest",
    "ModelTestResponse",
    # plan
    "DEFAULT_RUBRIC_WEIGHTS",
    "ApprovePlanRequest",
    "ApprovePlanResponse",
    "ClarificationAnswer",
    "ClarificationsRequest",
    "ClarifyingQuestion",
    "Plan",
    "PlanResponse",
    "PlanStep",
    "ReplanRequest",
    "ReportRubric",
    # report
    "REPORT_SECTION_KEYS",
    "REPORT_SECTION_TITLES",
    "Report",
    "ReportSection",
    # repo
    "RepoCard",
    "RepoDigest",
    # reproducibility
    "PaperMaterial",
    "ReproducibilityReport",
    "ReproducibilityScore",
    # task
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskPermissions",
    "TaskResponse",
    # validators
    "RepoUrlError",
]
