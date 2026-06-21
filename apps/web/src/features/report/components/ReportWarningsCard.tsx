import { AlertTriangle } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'

interface ReportWarningsCardProps {
  warnings?: string[]
  weakClaimCount?: number
  title?: string
}

export function ReportWarningsCard({
  warnings = [],
  weakClaimCount = 0,
  title = '风险提醒',
}: ReportWarningsCardProps) {
  if (warnings.length === 0 && weakClaimCount === 0) return null

  return (
    <Card className="border-amber-300 bg-amber-50">
      <CardContent className="space-y-3 pt-6">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden />
          <h2 className="text-lg font-semibold text-amber-900">{title}</h2>
        </div>
        {warnings.length > 0 && (
          <ul className="list-inside list-disc text-sm text-amber-900">
            {warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        )}
        {weakClaimCount > 0 && (
          <p className="text-sm text-amber-800">
            有 {weakClaimCount} 条结论为待确认或需要人工审阅，请在数据视图中核查证据。
          </p>
        )}
      </CardContent>
    </Card>
  )
}
