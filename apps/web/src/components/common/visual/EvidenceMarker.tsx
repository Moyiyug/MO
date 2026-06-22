import { ExternalLink } from 'lucide-react'

import { cn } from '@/lib/utils'
import { EVIDENCE_STRENGTH_COPY, SOURCE_TYPE_COPY } from '@/lib/uiCopy'
import type { EvidenceItem } from '@/types/evidence'

interface EvidenceMarkerProps {
  label: string
  item?: EvidenceItem
  onClick?: () => void
  className?: string
}

const STRENGTH_CLASS: Record<string, string> = {
  strong: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  medium: 'border-blue-300 bg-blue-50 text-blue-900',
  weak: 'border-amber-400 bg-amber-50 text-amber-900',
  missing: 'border-red-300 bg-red-50 text-red-900',
}

export function EvidenceMarker({
  label,
  item,
  onClick,
  className,
}: EvidenceMarkerProps) {
  const strengthCopy = item ? EVIDENCE_STRENGTH_COPY[item.strength] : null
  const sourceCopy = item ? SOURCE_TYPE_COPY[item.source_type] : null
  const markerClass =
    (item && STRENGTH_CLASS[item.strength]) ||
    'border-slate-300 bg-slate-50 text-slate-700'
  const title = item
    ? `${label} | ${sourceCopy?.label ?? item.source_type} | ${strengthCopy?.label ?? item.strength} | ${item.id}`
    : label

  const content = (
    <>
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-70" aria-hidden />
      <span className="min-w-0 truncate">{label}</span>
      {strengthCopy && <span className="shrink-0 opacity-75">{strengthCopy.label}</span>}
      {item?.source_uri?.startsWith('http') && (
        <ExternalLink className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
      )}
    </>
  )

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={title}
        className={cn(
          'inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors hover:border-blue-400 hover:text-blue-900',
          markerClass,
          className,
        )}
      >
        {content}
      </button>
    )
  }

  return (
    <span
      title={title}
      className={cn(
        'inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-xs',
        markerClass,
        className,
      )}
    >
      {content}
    </span>
  )
}
