import { Card, CardContent } from '@/components/ui/card'
import { REPORT_VIEW_COPY } from '@/lib/uiCopy'

interface ReportSeedDataPanelProps {
  seedNarratives?: string[]
  seedStructuredData?: unknown[]
}

export function ReportSeedDataPanel({
  seedNarratives,
  seedStructuredData,
}: ReportSeedDataPanelProps) {
  const hasNarratives = Array.isArray(seedNarratives) && seedNarratives.length > 0
  const hasStructuredData =
    Array.isArray(seedStructuredData) && seedStructuredData.length > 0

  if (!hasNarratives && !hasStructuredData) return null

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        {hasNarratives && (
          <section className="space-y-3">
            <h3 className="font-semibold">{REPORT_VIEW_COPY.seedNarratives}</h3>
            {seedNarratives.map((seed, index) => (
              <blockquote
                key={`${seed}-${index}`}
                className="rounded-md border-l-2 border-blue-300 bg-blue-50/35 px-3 py-2 text-sm text-muted-foreground"
              >
                {String(seed)}
              </blockquote>
            ))}
          </section>
        )}

        {hasStructuredData && (
          <section className="space-y-3">
            <h3 className="font-semibold">{REPORT_VIEW_COPY.seedStructuredData}</h3>
            {seedStructuredData.map((item, index) => (
              <details key={index} className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  数据快照 {index + 1}
                </summary>
                <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">
                  {JSON.stringify(item, null, 2)}
                </pre>
              </details>
            ))}
          </section>
        )}
      </CardContent>
    </Card>
  )
}
