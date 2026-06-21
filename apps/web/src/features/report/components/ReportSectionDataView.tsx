import { AlertTriangle } from 'lucide-react'

import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { Card, CardContent } from '@/components/ui/card'
import type { EvidenceLookup } from '@/lib/evidenceIndex'
import { REPORT_VIEW_COPY } from '@/lib/uiCopy'
import type { EvidenceItem } from '@/types/evidence'
import type { ReportSection } from '@/types/report'

import { ReportClaimList } from './ReportClaimList'
import { ReportSeedDataPanel } from './ReportSeedDataPanel'
import { ReportStructuredMarkdown } from './ReportStructuredMarkdown'
import { getPolishStatus, getStructuredMarkdown } from './reportViewUtils'

interface ReportSectionDataViewProps {
  section?: ReportSection
  evidenceItems?: EvidenceItem[]
  evidenceLookup: EvidenceLookup
  onViewEvidence?: (evidenceId: string) => void
}

export function ReportSectionDataView({
  section,
  evidenceItems,
  evidenceLookup,
  onViewEvidence,
}: ReportSectionDataViewProps) {
  if (!section) {
    return (
      <Card>
        <CardContent className="space-y-2 pt-6">
          <h2 className="text-lg font-semibold">章节不存在</h2>
          <p className="text-sm text-muted-foreground">请选择右侧目录中的报告章节。</p>
        </CardContent>
      </Card>
    )
  }

  const structured = getStructuredMarkdown(section)
  const polishWarnings = section.metadata?.polish_warnings ?? []
  const seedNarratives = section.metadata?.seed_narratives
  const seedStructuredData = section.metadata?.seed_structured_data

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <h2 className="text-xl font-semibold">{section.title}：数据视图</h2>
          <p className="text-sm text-muted-foreground">
            本页展示报告生成时保留的结构化草稿、章节种子、结论与证据。
          </p>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span>polish: {getPolishStatus(section)}</span>
            <span>claims: {section.claims.length}</span>
            <span>evidence: {(section.evidence_ids ?? []).length}</span>
          </div>
        </CardContent>
      </Card>

      {polishWarnings.length > 0 && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="pt-4 text-sm text-amber-900">
            <p className="font-medium">
              <AlertTriangle className="mr-1 inline h-4 w-4" aria-hidden />
              {REPORT_VIEW_COPY.polishWarnings}
            </p>
            <ul className="mt-2 list-inside list-disc">
              {polishWarnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{String(warning)}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <ReportStructuredMarkdown markdown={structured} />

      <Card>
        <CardContent className="space-y-3 pt-6">
          <h3 className="font-semibold">结论与证据</h3>
          <ReportClaimList
            claims={section.claims}
            evidenceLookup={evidenceLookup}
            onViewEvidence={onViewEvidence}
          />
          <EvidenceSummary
            evidenceIds={section.evidence_ids ?? []}
            evidenceItems={evidenceItems}
            onViewDetail={onViewEvidence}
          />
        </CardContent>
      </Card>

      <ReportSeedDataPanel
        seedNarratives={seedNarratives}
        seedStructuredData={seedStructuredData}
      />
    </div>
  )
}
