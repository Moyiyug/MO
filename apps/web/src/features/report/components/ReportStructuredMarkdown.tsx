import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { Card, CardContent } from '@/components/ui/card'
import { REPORT_VIEW_COPY } from '@/lib/uiCopy'

interface ReportStructuredMarkdownProps {
  markdown?: string
}

export function ReportStructuredMarkdown({
  markdown,
}: ReportStructuredMarkdownProps) {
  if (!markdown) return null

  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <h3 className="font-semibold">{REPORT_VIEW_COPY.structuredDraft}</h3>
        <SafeMarkdown markdown={markdown} />
      </CardContent>
    </Card>
  )
}
