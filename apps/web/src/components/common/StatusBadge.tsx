import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  NODE_STATUS_LABEL,
  NODE_STYLE,
  TASK_STATUS_STYLE,
} from '@/features/workflow/statusColor'
import type { NodeStatus, TaskStatus } from '@/types/enums'

const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  CREATED: '已创建',
  PLANNING: '计划中',
  WAITING_USER_CLARIFICATION: '等待澄清',
  WAITING_USER_APPROVAL: '等待批准',
  PLAN_APPROVED: '计划已批准',
  EXECUTING: '执行中',
  REPLANNING: '重规划中',
  REPORT_DRAFT: '报告草稿',
  REVIEW_REQUIRED: '待审阅',
  DONE: '已完成',
  FAILED: '失败',
}

interface TaskStatusBadgeProps {
  status: TaskStatus
  className?: string
}

export function TaskStatusBadge({ status, className }: TaskStatusBadgeProps) {
  const style = TASK_STATUS_STYLE[status] ?? 'bg-slate-100 text-slate-700'
  return (
    <Badge
      variant="outline"
      className={cn('border font-normal', style, className)}
      aria-label={`任务状态：${TASK_STATUS_LABEL[status]}`}
    >
      {TASK_STATUS_LABEL[status]}
    </Badge>
  )
}

interface NodeStatusBadgeProps {
  status: NodeStatus
  className?: string
}

export function NodeStatusBadge({ status, className }: NodeStatusBadgeProps) {
  const style = NODE_STYLE[status]
  return (
    <Badge
      variant="outline"
      className={cn('border font-normal', style, className)}
      aria-label={`节点状态：${NODE_STATUS_LABEL[status]}`}
    >
      {NODE_STATUS_LABEL[status]}
    </Badge>
  )
}
