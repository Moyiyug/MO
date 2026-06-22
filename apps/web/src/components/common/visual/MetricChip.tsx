import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type MetricTone = 'blue' | 'amber' | 'green' | 'red' | 'slate' | 'violet'

interface MetricChipProps {
  label: string
  value?: ReactNode
  icon?: ReactNode
  tone?: MetricTone
  title?: string
  className?: string
}

const TONE_CLASS: Record<MetricTone, string> = {
  blue: 'border-blue-300/80 bg-blue-50/70 text-blue-900',
  amber: 'border-amber-300/90 bg-amber-50/80 text-amber-900',
  green: 'border-emerald-300/80 bg-emerald-50/75 text-emerald-900',
  red: 'border-red-300/80 bg-red-50/75 text-red-900',
  slate: 'border-slate-300/80 bg-slate-50/75 text-slate-700',
  violet: 'border-violet-300/80 bg-violet-50/75 text-violet-900',
}

export function MetricChip({
  label,
  value,
  icon,
  tone = 'blue',
  title,
  className,
}: MetricChipProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex max-w-full min-w-0 items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium shadow-[0_1px_0_rgba(255,255,255,0.72)_inset]',
        TONE_CLASS[tone],
        className,
      )}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {value !== undefined && (
        <span className="shrink-0 font-mono text-[11px] tabular-nums">{value}</span>
      )}
      <span className="min-w-0 truncate">{label}</span>
    </span>
  )
}
