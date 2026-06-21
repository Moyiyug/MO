import { Link } from 'react-router-dom'

import { ClaimLabel } from '@/components/common/ClaimLabel'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { Card, CardContent } from '@/components/ui/card'
import type { ReportSection } from '@/types/report'

import { sectionDataPath, sectionPath } from './reportViewUtils'

interface ReportReaderSectionProps {
  taskId: string
  section?: ReportSection
  prev?: ReportSection | null
  next?: ReportSection | null
}

export function ReportReaderSection({
  taskId,
  section,
  prev,
  next,
}: ReportReaderSectionProps) {
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

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold">{section.title}</h2>
            {section.is_pending && <ClaimLabel label="pending" />}
          </div>
          {section.summary && (
            <p className="text-sm text-muted-foreground">{section.summary}</p>
          )}
          <SafeMarkdown markdown={section.markdown} />
          <div className="border-t pt-3">
            <Link
              to={sectionDataPath(taskId, section.key)}
              className="text-sm text-primary hover:underline"
            >
              查看本章数据、结论与证据
            </Link>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-2">
        {prev ? (
          <Link
            to={sectionPath(taskId, prev.key)}
            className="rounded-md border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            上一节：{prev.title}
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link
            to={sectionPath(taskId, next.key)}
            className="rounded-md border px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            下一节：{next.title}
          </Link>
        )}
      </div>
    </div>
  )
}
