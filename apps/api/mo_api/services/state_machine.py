"""任务状态机（PRD §4）。

定义合法状态迁移表，供本里程碑及后续里程碑共用。
M1 仅实际使用 CREATED -> PLANNING，但迁移表一次性按 PRD 完整声明。

允许流（PRD §4）::

    CREATED -> PLANNING
    PLANNING -> WAITING_USER_CLARIFICATION -> PLANNING
    PLANNING -> WAITING_USER_APPROVAL -> PLAN_APPROVED
    PLAN_APPROVED -> EXECUTING
    EXECUTING -> REPLANNING -> WAITING_USER_APPROVAL -> EXECUTING
    EXECUTING -> REPORT_DRAFT -> REVIEW_REQUIRED -> DONE
    any -> FAILED
"""

from __future__ import annotations

from ..models.enums import TaskStatus

# 每个状态可迁移到的目标状态集合（不含通用的 -> FAILED）
ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.PLANNING},
    TaskStatus.PLANNING: {
        TaskStatus.WAITING_USER_CLARIFICATION,
        TaskStatus.WAITING_USER_APPROVAL,
    },
    TaskStatus.WAITING_USER_CLARIFICATION: {TaskStatus.PLANNING},
    # M2 扩展：重生成(PLANNING)、replan(REPLANNING)、批准(PLAN_APPROVED)
    TaskStatus.WAITING_USER_APPROVAL: {
        TaskStatus.PLANNING,
        TaskStatus.PLAN_APPROVED,
        TaskStatus.REPLANNING,
    },
    TaskStatus.PLAN_APPROVED: {
        TaskStatus.EXECUTING,
        TaskStatus.REPLANNING,
        TaskStatus.PLANNING,
    },
    TaskStatus.EXECUTING: {
        TaskStatus.REPLANNING,
        TaskStatus.REPORT_DRAFT,
    },
    TaskStatus.REPLANNING: {
        TaskStatus.WAITING_USER_APPROVAL,
        TaskStatus.WAITING_USER_CLARIFICATION,
    },
    TaskStatus.REPORT_DRAFT: {
        TaskStatus.REVIEW_REQUIRED,
        TaskStatus.PLANNING,
        TaskStatus.REPLANNING,
    },
    TaskStatus.REVIEW_REQUIRED: {
        TaskStatus.DONE,
        TaskStatus.PLANNING,
        TaskStatus.REPLANNING,
    },
    TaskStatus.DONE: {TaskStatus.PLANNING, TaskStatus.REPLANNING},
    # 执行失败后允许回到 PlanMode 重新生成/重规划
    TaskStatus.FAILED: {TaskStatus.PLANNING, TaskStatus.REPLANNING},
}


class InvalidTransitionError(ValueError):
    """非法状态迁移。"""


def can_transition(src: TaskStatus, dst: TaskStatus) -> bool:
    """判断 src -> dst 是否合法。任意状态都可迁移到 FAILED。"""
    if dst is TaskStatus.FAILED:
        return True
    return dst in ALLOWED_TRANSITIONS.get(src, set())


def ensure_transition(src: TaskStatus, dst: TaskStatus) -> None:
    """非法迁移时抛 InvalidTransitionError。"""
    if not can_transition(src, dst):
        raise InvalidTransitionError(f"illegal transition: {src.value} -> {dst.value}")
