import { memo } from 'react'
import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import { AlertTriangle } from 'lucide-react'

import { NodeStatusBadge } from '@/components/common/StatusBadge'
import { NODE_STYLE } from '@/features/workflow/statusColor'
import { cn } from '@/lib/utils'

import type { StepNodeData } from './buildGraph'

function StepNodeComponent({ data }: NodeProps<Node<StepNodeData>>) {
  const { step, displayStatus } = data
  const isHighRisk =
    step.risk_level === 'high' || step.requires_approval

  return (
    <div
      className={cn(
        'min-w-[200px] max-w-[240px] rounded-lg border-2 px-3 py-2 shadow-sm',
        NODE_STYLE[displayStatus],
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-400" />
      <div className="flex flex-col gap-1.5">
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-medium leading-tight">{step.title}</span>
          {isHighRisk && (
            <AlertTriangle
              className="h-4 w-4 shrink-0 text-amber-600"
              aria-label="高风险步骤"
            />
          )}
        </div>
        <NodeStatusBadge status={displayStatus} />
        <span className="text-xs text-muted-foreground">{step.tool}</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-slate-400" />
    </div>
  )
}

export const StepNode = memo(StepNodeComponent)
