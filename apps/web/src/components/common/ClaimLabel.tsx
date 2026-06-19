import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { CLAIM_LABEL_COPY } from '@/lib/uiCopy'
import type { ClaimLabel as ClaimLabelType } from '@/types/enums'

const CLAIM_STYLES: Record<ClaimLabelType, string> = {
  fact: 'bg-emerald-50 text-emerald-800 border-emerald-300',
  inference: 'bg-blue-50 text-blue-800 border-blue-300',
  recommendation: 'bg-violet-50 text-violet-800 border-violet-300',
  pending: 'bg-amber-50 text-amber-900 border-amber-500',
}

interface ClaimLabelProps {
  label: ClaimLabelType
  className?: string
}

export function ClaimLabel({ label, className }: ClaimLabelProps) {
  const copy = CLAIM_LABEL_COPY[label]
  const text = copy?.label ?? label

  return (
    <Badge
      variant="outline"
      className={cn('border font-normal', CLAIM_STYLES[label], className)}
      aria-label={`论断标签：${text}`}
    >
      {text}
    </Badge>
  )
}
