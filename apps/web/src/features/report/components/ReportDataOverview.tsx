import { Link } from 'react-router-dom'
import { Database } from 'lucide-react'

import { MetricChip } from '@/components/common/visual'
import { Card, CardContent } from '@/components/ui/card'
import type { ReportResponse } from '@/types/report'

import { getPolishStatus, sectionDataPath } from './reportViewUtils'

interface ReportDataOverviewProps {
  taskId: string
  report: ReportResponse
}

export function ReportDataOverview({ taskId, report }: ReportDataOverviewProps) {
  const synthesis = report.research_synthesis
  const quality = report.research_quality
  const totalClaims = report.sections.reduce(
    (sum, section) => sum + section.claims.length,
    0,
  )
  const totalSectionEvidence = report.sections.reduce(
    (sum, section) => sum + (section.evidence_ids ?? []).length,
    0,
  )

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-muted-foreground" aria-hidden />
            <h2 className="text-lg font-semibold">数据事实层</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            这里展示报告生成时保留的结构化数据、结论与证据。默认阅读视图不会直接展示这些内容。
          </p>
          <div className="grid gap-2 text-sm md:grid-cols-2">
            <div>报告版本：{report.report_version ?? 'unknown'}</div>
            <div>生成时间：{new Date(report.generated_at).toLocaleString()}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <MetricChip label="章节" value={report.sections.length} tone="slate" />
            <MetricChip label="待确认" value={report.pending_warnings.length} tone="amber" />
            <MetricChip label="结论" value={totalClaims} tone="violet" />
            <MetricChip label="章节证据" value={totalSectionEvidence} tone="green" />
          </div>
        </CardContent>
      </Card>

      {/* 研究综合与质量 */}
      {(synthesis || quality) && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-lg font-semibold">研究综合与质量评估</h2>
            {synthesis && (
              <div className="space-y-2 text-sm">
                <div>
                  <span className="font-medium">核心论点：</span>
                  {synthesis.thesis || '（无）'}
                </div>
                {synthesis.key_insights.length > 0 && (
                  <div>
                    <span className="font-medium">关键洞察：</span>
                    <ul className="list-disc pl-5 space-y-1 mt-1">
                      {synthesis.key_insights.map((insight, i) => (
                        <li key={i}>{insight}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {synthesis.uncertainty.length > 0 && (
                  <div>
                    <span className="font-medium">不确定性与边界：</span>
                    <ul className="list-disc pl-5 space-y-1 mt-1">
                      {synthesis.uncertainty.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {synthesis.next_questions.length > 0 && (
                  <div>
                    <span className="font-medium">下一步验证：</span>
                    <ul className="list-disc pl-5 space-y-1 mt-1">
                      {synthesis.next_questions.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            {quality && (
              <div className="grid gap-2 text-sm md:grid-cols-3 border-t pt-3">
                <div>研究深度：{quality.research_depth}</div>
                <div>置信度：{quality.confidence_level}</div>
                <div>证据覆盖率：{(quality.evidence_coverage * 100).toFixed(0)}%</div>
                <div>PaperQA 回答：{quality.has_paperqa_answer ? '有' : '无'}</div>
                <div>联网报告：{quality.has_web_report ? '有' : '无'}</div>
                <div>Weak/Missing 证据：{quality.weak_or_missing_evidence_count}</div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="space-y-3 pt-6">
          <h2 className="text-lg font-semibold">章节数据</h2>
          <div className="space-y-2">
            {report.sections.map((section) => (
              <Link
                key={section.key}
                to={sectionDataPath(taskId, section.key)}
                className="block rounded-lg border p-3 transition-colors hover:border-blue-300 hover:bg-blue-50/50"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{section.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {section.claims.length} 条结论 / {(section.evidence_ids ?? []).length} 条章节证据
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  polish: {getPolishStatus(section)}
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>

      {report.evidence_appendix_groups && report.evidence_appendix_groups.length > 0 && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-lg font-semibold">证据附录分组</h2>
            <div className="grid gap-2 md:grid-cols-2">
              {report.evidence_appendix_groups.map((group) => (
                <div key={group.key} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{group.title}</p>
                  <p className="mt-1 text-muted-foreground">
                    {group.evidence_ids.length} 条证据
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
