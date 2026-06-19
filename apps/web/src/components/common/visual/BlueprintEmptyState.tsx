import type { ReactNode } from 'react'
import { Archive } from 'lucide-react'

import { BlueprintPanel } from './BlueprintPanel'

interface BlueprintEmptyStateProps {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
}

export function BlueprintEmptyState({
  title,
  description,
  icon,
  action,
}: BlueprintEmptyStateProps) {
  return (
    <BlueprintPanel
      label="empty record"
      className="mx-auto max-w-xl"
      contentClassName="flex flex-col items-center gap-3 px-6 py-12 text-center"
    >
      <div className="relative flex h-14 w-14 items-center justify-center rounded-full border border-blue-300/70 bg-blue-50/70 text-blue-800">
        <span className="absolute h-20 w-px bg-[var(--mo-line)]" aria-hidden />
        <span className="absolute h-px w-20 bg-[var(--mo-line)]" aria-hidden />
        <span className="relative rounded-full bg-background/80 p-3">
          {icon ?? <Archive className="h-5 w-5" aria-hidden />}
        </span>
      </div>
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        {description && (
          <p className="max-w-md text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="pt-1">{action}</div>}
    </BlueprintPanel>
  )
}
