import { useState } from 'react'
import { ChevronDown, ChevronRight, ExternalLink, FileText } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { buildEvidenceLookup, isExternalEvidenceSource } from '@/lib/evidenceIndex'
import { cn } from '@/lib/utils'
import {
  EVIDENCE_STRENGTH_COPY,
  SOURCE_TYPE_COPY,
} from '@/lib/uiCopy'
import type { EvidenceItem } from '@/types/evidence'

export interface EvidenceSummaryProps {
  evidenceIds: string[]
  evidenceItems?: EvidenceItem[]
  strengthDistribution?: Partial<Record<string, number>>
  defaultExpanded?: boolean
  onViewDetail?: (evidenceId: string) => void
  className?: string
}

export function EvidenceSummary({
  evidenceIds,
  evidenceItems,
  strengthDistribution,
  defaultExpanded = false,
  onViewDetail,
  className,
}: EvidenceSummaryProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const lookup = buildEvidenceLookup(evidenceItems)

  if (evidenceIds.length === 0) {
    return (
      <div className={cn('text-xs text-muted-foreground', className)}>
        暂无证据
      </div>
    )
  }

  const distText =
    strengthDistribution
      ? Object.entries(strengthDistribution)
          .filter(([, count]) => (count ?? 0) > 0)
          .map(([key, count]) => `${count} ${key}`)
          .join(' / ')
      : null

  return (
    <div className={cn('text-sm', className)}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1.5 text-muted-foreground transition-colors hover:text-foreground"
        aria-expanded={expanded}
      >
        <FileText className="h-3.5 w-3.5" aria-hidden />
        <span>
          {evidenceIds.length} 条证据
          {distText && `（${distText}）`}
        </span>
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5" aria-hidden />
        ) : (
          <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        )}
      </button>

      {expanded && (
        <ul className="mt-2 space-y-2">
          {evidenceIds.map((id) => {
            const item = lookup.byId.get(id)
            const displayId = lookup.labelById.get(id) ?? id
            const sourceCopy = item ? SOURCE_TYPE_COPY[item.source_type] : null
            const strengthCopy = item ? EVIDENCE_STRENGTH_COPY[item.strength] : null
            const sourceIsLink = item ? isExternalEvidenceSource(item.source_uri) : false

            return (
              <li
                id={`evidence-${id}`}
                key={id}
                className="rounded-md border bg-background/70 p-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{displayId}</Badge>
                  {sourceCopy && (
                    <span className="text-xs text-muted-foreground">
                      {sourceCopy.label}
                    </span>
                  )}
                  {strengthCopy && (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      {strengthCopy.label}
                    </span>
                  )}
                  {onViewDetail && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-6 px-2"
                      onClick={() => onViewDetail(id)}
                    >
                      定位
                    </Button>
                  )}
                </div>

                {item ? (
                  <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                    <p className="line-clamp-2">{item.quote_or_summary}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      {sourceIsLink ? (
                        <a
                          href={item.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex max-w-full items-center gap-1 text-primary hover:underline"
                        >
                          <span className="truncate">{item.source_uri}</span>
                          <ExternalLink className="h-3 w-3 flex-shrink-0" aria-hidden />
                        </a>
                      ) : (
                        <span className="max-w-full truncate rounded bg-muted px-1.5 py-0.5">
                          {item.source_uri}
                        </span>
                      )}
                      {item.locator && <span>{item.locator}</span>}
                    </div>
                  </div>
                ) : (
                  <code className="mt-2 block truncate rounded bg-muted px-1.5 py-0.5 text-xs">
                    {id}
                  </code>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
