import { AlertTriangle } from 'lucide-react'

import { ClaimLabel } from '@/components/common/ClaimLabel'
import type { EvidenceLookup } from '@/lib/evidenceIndex'
import { cn } from '@/lib/utils'
import type { ReportClaim } from '@/types/report'

import { ReportEvidenceRefs } from './ReportEvidenceRefs'

interface ReportClaimListProps {
  claims: ReportClaim[]
  evidenceLookup: EvidenceLookup
  onViewEvidence?: (evidenceId: string) => void
}

function isWeakClaim(claim: ReportClaim): boolean {
  return claim.label === 'pending' || claim.requires_user_review === true
}

export function ReportClaimList({
  claims,
  evidenceLookup,
  onViewEvidence,
}: ReportClaimListProps) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted-foreground">暂无结论</p>
  }

  return (
    <ul className="space-y-3">
      {claims.map((claim) => {
        const weak = isWeakClaim(claim)
        return (
          <li
            key={claim.id}
            className={cn(
              'rounded-md border p-3 text-sm',
              weak ? 'border-amber-300 bg-amber-50' : 'bg-background',
            )}
          >
            <div className="flex flex-wrap items-start gap-2">
              <ClaimLabel label={claim.label} />
              <span className="min-w-0 flex-1">{claim.claim}</span>
              {weak && (
                <span className="text-xs text-amber-700">
                  <AlertTriangle className="mr-0.5 inline h-3 w-3" aria-hidden />
                  需进一步验证
                </span>
              )}
            </div>
            <ReportEvidenceRefs
              evidenceIds={claim.evidence_ids}
              evidenceLookup={evidenceLookup}
              onViewDetail={onViewEvidence}
            />
          </li>
        )
      })}
    </ul>
  )
}
