import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { Card, CardContent } from '@/components/ui/card'
import type { ReportResponse } from '@/types/report'

import { ReportWarningsCard } from './ReportWarningsCard'

export function ReportReaderFull({ report }: { report: ReportResponse }) {
  return (
    <div className="space-y-4">
      <ReportWarningsCard warnings={report.pending_warnings} />
      <Card>
        <CardContent className="pt-6">
          <SafeMarkdown markdown={report.markdown} />
        </CardContent>
      </Card>
    </div>
  )
}
