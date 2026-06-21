import { ShieldAlert } from 'lucide-react'

import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { Card, CardContent } from '@/components/ui/card'
import type { EvidenceLookup } from '@/lib/evidenceIndex'
import type { EvidenceItem } from '@/types/evidence'
import type { ReportResponse } from '@/types/report'

import { ReportClaimList } from './ReportClaimList'

interface ReportEvidenceViewProps {
  report: ReportResponse
  evidenceItems?: EvidenceItem[]
  allEvidenceIds: string[]
  evidenceLookup: EvidenceLookup
  onViewDetail: (evidenceId: string) => void
}

export function ReportEvidenceView({
  report,
  evidenceItems,
  allEvidenceIds,
  evidenceLookup,
  onViewDetail,
}: ReportEvidenceViewProps) {
  const groups = report.evidence_appendix_groups ?? []
  const claimsWithEvidence = report.sections
    .flatMap((section) => section.claims)
    .filter((claim) => claim.evidence_ids.length > 0)

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-700" aria-hidden />
            <h2 className="text-lg font-semibold">证据附录</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            这里集中展示完整证据链、来源定位和与结论的映射。弱证据和缺失证据不会被隐藏。
          </p>
        </CardContent>
      </Card>

      {groups.length > 0 ? (
        groups.map((group) => (
          <Card key={group.key}>
            <CardContent className="space-y-3 pt-6">
              <h3 className="font-semibold">{group.title}</h3>
              <EvidenceSummary
                evidenceIds={group.evidence_ids}
                evidenceItems={evidenceItems}
                defaultExpanded
                onViewDetail={onViewDetail}
              />
            </CardContent>
          </Card>
        ))
      ) : (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h3 className="font-semibold">全部证据</h3>
            <EvidenceSummary
              evidenceIds={allEvidenceIds}
              evidenceItems={evidenceItems}
              defaultExpanded
              onViewDetail={onViewDetail}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-3 pt-6">
          <h3 className="font-semibold">结论到证据的映射</h3>
          <ReportClaimList
            claims={claimsWithEvidence}
            evidenceLookup={evidenceLookup}
            onViewEvidence={onViewDetail}
          />
        </CardContent>
      </Card>
    </div>
  )
}
