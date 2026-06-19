import { useState } from 'react'
import { ChevronDown, ChevronRight, ExternalLink, FileText } from 'lucide-react'

import { EvidenceMarker } from '@/components/common/visual'
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
      <div
        className={cn(
          'inline-flex rounded-md border border-dashed border-[var(--mo-line)] bg-background/55 px-2 py-1 text-xs text-muted-foreground',
          className,
        )}
      >
        暂无证据
      </div>
    )
  }

  const distText =
    strengthDistribution
      ? Object.entries(strengthDistribution)
          .filter(([, count]) => (count ?? 0) > 0)
          .map(([key, count]) => {
            const label =
              EVIDENCE_STRENGTH_COPY[
                key as keyof typeof EVIDENCE_STRENGTH_COPY
              ]?.label ?? key
            return `${count} ${label}`
          })
          .join(' / ')
      : null

  return (
    <div className={cn('min-w-0 text-sm', className)}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-[var(--mo-line)] bg-background/55 px-2 py-1 text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-800"
        aria-expanded={expanded}
      >
        <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="min-w-0 truncate">
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
        <ul className="mt-2 max-h-[22rem] space-y-2 overflow-y-auto pr-1">
          {evidenceIds.map((id) => {
            const item = lookup.byId.get(id)
            const displayId = lookup.labelById.get(id) ?? id
            const sourceCopy = item ? SOURCE_TYPE_COPY[item.source_type] : null
            const sourceIsLink = item ? isExternalEvidenceSource(item.source_uri) : false

            return (
              <li
                id={`evidence-${id}`}
                key={id}
                className="min-w-0 rounded-md border border-[var(--mo-line)] bg-background/70 p-2 shadow-[var(--mo-shadow-line)]"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <EvidenceMarker
                    label={displayId}
                    item={item}
                    onClick={onViewDetail ? () => onViewDetail(id) : undefined}
                  />
                  {sourceCopy && (
                    <span className="rounded border border-[var(--mo-line)] bg-background/60 px-1.5 py-0.5 text-xs text-muted-foreground">
                      {sourceCopy.label}
                    </span>
                  )}
                </div>

                {item ? (
                  <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                    <p className="line-clamp-2 break-words">{item.quote_or_summary}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      {sourceIsLink ? (
                        <a
                          href={item.source_uri}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex min-w-0 max-w-full items-center gap-1 text-primary hover:underline"
                        >
                          <span className="truncate">{item.source_uri}</span>
                          <ExternalLink className="h-3 w-3 flex-shrink-0" aria-hidden />
                        </a>
                      ) : (
                        <span className="max-w-full truncate rounded border border-[var(--mo-line)] bg-muted/55 px-1.5 py-0.5">
                          {item.source_uri}
                        </span>
                      )}
                      {item.locator && <span className="break-all">{item.locator}</span>}
                    </div>
                  </div>
                ) : (
                  <code className="mt-2 block break-all rounded bg-muted px-1.5 py-0.5 text-xs">
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
