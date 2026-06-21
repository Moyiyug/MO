import type { EvidenceLookup } from '@/lib/evidenceIndex'
import { getEvidenceLabel } from '@/lib/evidenceIndex'

interface ReportEvidenceRefsProps {
  evidenceIds: string[]
  evidenceLookup: EvidenceLookup
  onViewDetail?: (evidenceId: string) => void
}

export function ReportEvidenceRefs({
  evidenceIds,
  evidenceLookup,
  onViewDetail,
}: ReportEvidenceRefsProps) {
  if (evidenceIds.length === 0) return null

  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {evidenceIds.map((id) => {
        const item = evidenceLookup.byId.get(id)
        const label = getEvidenceLabel(id, evidenceLookup)
        if (!item) {
          return (
            <span
              key={id}
              className="rounded-md border border-dashed px-2 py-0.5 text-xs text-muted-foreground"
              title={id}
            >
              {label}
            </span>
          )
        }
        return (
          <button
            key={id}
            type="button"
            onClick={() => onViewDetail?.(id)}
            className="rounded-md border bg-muted px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-700"
            title={item.quote_or_summary}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
