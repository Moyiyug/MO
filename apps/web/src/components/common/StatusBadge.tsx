import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  XCircle,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { TASK_STATUS_COPY, NODE_STATUS_COPY } from '@/lib/uiCopy'
import {
  NODE_STYLE,
  TASK_STATUS_STYLE,
} from '@/features/workflow/statusColor'
import type { NodeStatus, TaskStatus } from '@/types/enums'

// ─── 图标映射 ────────────────────────────────────────────────────────

const TASK_STATUS_ICON: Partial<Record<TaskStatus, ReactNode>> = {
  PLANNING: <Loader2 className="h-3 w-3 animate-spin" aria-hidden />,
  EXECUTING: <Loader2 className="h-3 w-3 animate-spin" aria-hidden />,
  WAITING_USER_CLARIFICATION: <AlertCircle className="h-3 w-3" aria-hidden />,
  WAITING_USER_APPROVAL: <AlertCircle className="h-3 w-3" aria-hidden />,
  REVIEW_REQUIRED: <AlertCircle className="h-3 w-3" aria-hidden />,
  DONE: <CheckCircle2 className="h-3 w-3" aria-hidden />,
  FAILED: <XCircle className="h-3 w-3" aria-hidden />,
}

const NODE_STATUS_ICON: Partial<Record<NodeStatus, ReactNode>> = {
  running: <Loader2 className="h-3 w-3 animate-spin" aria-hidden />,
  waiting_user: <AlertCircle className="h-3 w-3" aria-hidden />,
  completed: <CheckCircle2 className="h-3 w-3" aria-hidden />,
  failed: <XCircle className="h-3 w-3" aria-hidden />,
}

// ─── TaskStatusBadge ───────────────────────────────────────────────

interface TaskStatusBadgeProps {
  status: TaskStatus
  className?: string
  /** 是否显示图标，默认 true */
  showIcon?: boolean
}

export function TaskStatusBadge({
  status,
  className,
  showIcon = true,
}: TaskStatusBadgeProps) {
  const copy = TASK_STATUS_COPY[status]
  const label = copy?.label ?? status
  const style = TASK_STATUS_STYLE[status] ?? 'bg-slate-100 text-slate-700'
  const icon = showIcon ? TASK_STATUS_ICON[status] : null

  return (
    <Badge
      variant="outline"
      className={cn('border font-normal inline-flex items-center gap-1', style, className)}
      aria-label={`任务状态：${label}`}
    >
      {icon}
      {label}
    </Badge>
  )
}

// ─── NodeStatusBadge ────────────────────────────────────────────────

interface NodeStatusBadgeProps {
  status: NodeStatus
  className?: string
  /** 是否显示图标，默认 true */
  showIcon?: boolean
}

export function NodeStatusBadge({
  status,
  className,
  showIcon = true,
}: NodeStatusBadgeProps) {
  const copy = NODE_STATUS_COPY[status]
  const label = copy?.label ?? status
  const style = NODE_STYLE[status]
  const icon = showIcon ? NODE_STATUS_ICON[status] : null

  return (
    <Badge
      variant="outline"
      className={cn('border font-normal inline-flex items-center gap-1', style, className)}
      aria-label={`节点状态：${label}`}
    >
      {icon}
      {label}
    </Badge>
  )
}
