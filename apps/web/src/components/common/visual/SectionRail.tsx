import type { ReactNode } from 'react'
import { CheckCircle2, Circle, CircleAlert, CircleDot, XCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { NodeStatus } from '@/types/enums'

type RailStatus = NodeStatus | 'active'

export interface SectionRailItem {
  id: string
  label: string
  description?: ReactNode
  status?: RailStatus
  onClick?: () => void
}

interface SectionRailProps {
  items: SectionRailItem[]
  className?: string
}

const STATUS_CLASS: Record<RailStatus, string> = {
  active: 'border-blue-500 bg-blue-50 text-blue-800',
  pending: 'border-slate-300 bg-slate-50 text-slate-600',
  running: 'border-blue-500 bg-blue-50 text-blue-800 mo-node-running',
  waiting_user: 'border-amber-500 bg-amber-50 text-amber-900 mo-node-waiting',
  completed: 'border-emerald-400 bg-emerald-50 text-emerald-800',
  failed: 'border-red-500 bg-red-50 text-red-800',
  skipped: 'border-slate-200 bg-slate-100 text-slate-500',
}

function RailIcon({ status }: { status: RailStatus }) {
  if (status === 'completed') return <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
  if (status === 'failed') return <XCircle className="h-3.5 w-3.5" aria-hidden />
  if (status === 'waiting_user') return <CircleAlert className="h-3.5 w-3.5" aria-hidden />
  if (status === 'running' || status === 'active') {
    return <CircleDot className="h-3.5 w-3.5" aria-hidden />
  }
  return <Circle className="h-3.5 w-3.5" aria-hidden />
}

export function SectionRail({ items, className }: SectionRailProps) {
  return (
    <ol className={cn('space-y-0', className)}>
      {items.map((item, index) => {
        const status = item.status ?? 'pending'
        const content = (
          <>
            <span
              className={cn(
                'relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[10px] shadow-sm',
                STATUS_CLASS[status],
              )}
            >
              <RailIcon status={status} />
            </span>
            <span className="min-w-0 flex-1 pb-4">
              <span className="block truncate text-sm font-medium">{item.label}</span>
              {item.description && (
                <span className="mt-0.5 block break-words text-xs leading-5 text-muted-foreground">
                  {item.description}
                </span>
              )}
            </span>
          </>
        )

        return (
          <li key={item.id} className="relative flex gap-3">
            {index < items.length - 1 && (
              <span
                className="absolute left-[13px] top-7 h-[calc(100%-1.75rem)] w-px bg-[var(--mo-line)]"
                aria-hidden
              />
            )}
            {item.onClick ? (
              <button
                type="button"
                onClick={item.onClick}
                className="flex min-w-0 flex-1 gap-3 rounded-md text-left transition-colors hover:bg-blue-50/60"
              >
                {content}
              </button>
            ) : (
              <div className="flex min-w-0 flex-1 gap-3">{content}</div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
