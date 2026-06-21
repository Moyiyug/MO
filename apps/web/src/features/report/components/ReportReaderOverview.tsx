import { Link } from 'react-router-dom'
import { BookOpen, Database, FileText, ShieldAlert } from 'lucide-react'

import { ClaimLabel } from '@/components/common/ClaimLabel'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { MetricChip } from '@/components/common/visual'
import { Card, CardContent } from '@/components/ui/card'
import { REPORT_VIEW_COPY } from '@/lib/uiCopy'
import type { ReportResponse } from '@/types/report'

import { ReportWarningsCard } from './ReportWarningsCard'

interface ReportReaderOverviewProps {
  taskId: string
  taskGoal?: string
  report: ReportResponse
  repoCount: number
  pendingCount: number
  weakClaimCount: number
}

export function ReportReaderOverview({
  taskId,
  taskGoal,
  report,
  repoCount,
  pendingCount,
  weakClaimCount,
}: ReportReaderOverviewProps) {
  const findings = report.key_findings ?? []
  const recommendations = report.recommendation_summary ?? []

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" aria-hidden />
            <h2 className="text-lg font-semibold">报告摘要</h2>
          </div>
          <SafeMarkdown
            markdown={
              report.executive_summary ||
              `本次调研围绕「${taskGoal ?? '未命名任务'}」展开。`
            }
          />
          <div className="flex flex-wrap gap-2">
            <MetricChip label="仓库" value={repoCount} />
            <MetricChip label="章节" value={report.sections.length} tone="slate" />
            {pendingCount > 0 && (
              <MetricChip label="待确认" value={pendingCount} tone="amber" />
            )}
          </div>
        </CardContent>
      </Card>

      {findings.length > 0 && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-lg font-semibold">关键发现</h2>
            <div className="grid gap-3 md:grid-cols-2">
              {findings.slice(0, 6).map((finding, index) => (
                <div
                  key={`${finding.title}-${index}`}
                  className="rounded-lg border bg-background/70 p-3"
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <ClaimLabel label={finding.label} />
                    {finding.requires_user_review && (
                      <span className="text-xs text-amber-700">需审阅</span>
                    )}
                  </div>
                  <p className="text-sm font-medium">{finding.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {finding.summary}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {recommendations.length > 0 && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-lg font-semibold">场景化建议</h2>
            <div className="space-y-3">
              {recommendations.map((rec) => (
                <div key={rec.scenario} className="rounded-lg border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <p className="font-medium">{rec.scenario}</p>
                    {rec.requires_user_review && (
                      <span className="text-xs text-amber-700">需审阅</span>
                    )}
                  </div>
                  <p className="text-sm">{rec.recommendation}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{rec.rationale}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <ReportWarningsCard
        warnings={report.pending_warnings}
        weakClaimCount={weakClaimCount}
      />

      <Card>
        <CardContent className="space-y-3 pt-6">
          <h2 className="text-lg font-semibold">阅读入口</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Link
              to={`/tasks/${taskId}/report/full`}
              className="rounded-lg border bg-muted/25 p-4 transition-colors hover:border-blue-300 hover:bg-blue-50"
            >
              <BookOpen className="mb-2 h-4 w-4 text-blue-700" aria-hidden />
              <p className="font-medium">{REPORT_VIEW_COPY.readerFull.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {REPORT_VIEW_COPY.readerFull.description}
              </p>
            </Link>
            <div className="rounded-lg border p-4">
              <FileText className="mb-2 h-4 w-4 text-slate-700" aria-hidden />
              <p className="font-medium">按章节阅读</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {report.sections.slice(0, 6).map((section) => (
                  <Link
                    key={section.key}
                    to={`/tasks/${taskId}/report/sections/${section.key}`}
                    className="rounded-md border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-700"
                  >
                    {section.title}
                  </Link>
                ))}
              </div>
            </div>
            <Link
              to={`/tasks/${taskId}/report/data`}
              className="rounded-lg border bg-muted/25 p-4 transition-colors hover:border-blue-300 hover:bg-blue-50"
            >
              <Database className="mb-2 h-4 w-4 text-blue-700" aria-hidden />
              <p className="font-medium">{REPORT_VIEW_COPY.dataOverview.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {REPORT_VIEW_COPY.dataOverview.description}
              </p>
            </Link>
            <Link
              to={`/tasks/${taskId}/report/evidence`}
              className="rounded-lg border bg-muted/25 p-4 transition-colors hover:border-blue-300 hover:bg-blue-50"
            >
              <ShieldAlert className="mb-2 h-4 w-4 text-amber-700" aria-hidden />
              <p className="font-medium">{REPORT_VIEW_COPY.evidence.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                弱证据、缺失证据和来源定位在这里集中查看。
              </p>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
