import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { OrnamentLayer } from './OrnamentLayer'
import type { OrnamentVariant } from './ornamentTypes'

interface VisualGuideCardProps {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
  steps?: string[]
  ornament?: OrnamentVariant
  className?: string
}

export function VisualGuideCard({
  eyebrow,
  title,
  description,
  action,
  steps,
  ornament = 'route',
  className,
}: VisualGuideCardProps) {
  return (
    <aside
      className={cn(
        'mo-ornament-host mo-blueprint-panel rounded-lg border p-4',
        className,
      )}
    >
      <OrnamentLayer
        variant={ornament}
        placement="top-right"
        density="low"
      />
      <div className="mo-ornament-content space-y-3">
        {eyebrow && (
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            {eyebrow}
          </p>
        )}
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          {description && (
            <p className="text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {steps && steps.length > 0 && (
          <ol className="space-y-2 text-xs text-muted-foreground">
            {steps.map((step, index) => (
              <li key={step} className="flex gap-2">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border bg-background/70 font-mono text-[10px]">
                  {index + 1}
                </span>
                <span className="min-w-0 break-words">{step}</span>
              </li>
            ))}
          </ol>
        )}
        {action && <div className="pt-1">{action}</div>}
      </div>
    </aside>
  )
}
