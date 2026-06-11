import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import {
  useConfirmReport,
  useExportReport,
  useRegenerateReport,
  useReport,
} from '@/api/report'
import { useTask } from '@/api/tasks'
import { ClaimLabel } from '@/components/common/ClaimLabel'
import { QueryState } from '@/components/common/QueryState'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { ReportClaim } from '@/types/report'

/** P-007 Report — F-011 安全渲染 + claim 标签 + evidence 跳转 + 导出 */
export function ReportPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task, isLoading: taskLoading, isError: taskError, error: taskErr, refetch: refetchTask } = useTask(taskId)

  const hasReport =
    task?.status === 'REPORT_DRAFT' ||
    task?.status === 'REVIEW_REQUIRED' ||
    task?.status === 'DONE'

  const {
    data: report,
    isLoading: reportLoading,
    isError: reportError,
    error: reportErr,
    refetch: refetchReport,
  } = useReport(taskId, hasReport)

  const confirmMutation = useConfirmReport()
  const exportMutation = useExportReport()
  const regenerateMutation = useRegenerateReport()

  const scrollToEvidence = useCallback((evidenceId: string) => {
    const el = document.getElementById(`evidence-${evidenceId}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handleExport = () => {
    if (!taskId) return
    exportMutation.mutate(taskId, {
      onSuccess: () => toast.success('报告已导出'),
      onError: (e) => toast.error(e instanceof Error ? e.message : '导出失败'),
    })
  }

  const handleRegenerate = () => {
    if (!taskId) return
    regenerateMutation.mutate(taskId, {
      onSuccess: () => toast.success('报告已重新生成'),
      onError: (e) => toast.error(e instanceof Error ? e.message : '重新生成失败'),
    })
  }

  const handleConfirm = () => {
    if (!taskId) return
    confirmMutation.mutate(taskId, {
      onSuccess: () => toast.success('报告已确认'),
      onError: (e) => toast.error(e instanceof Error ? e.message : '确认失败'),
    })
  }

  const isLoading = taskLoading || (hasReport && reportLoading)
  const isError = taskError || reportError
  const error = taskErr ?? reportErr

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError}
      error={error}
      onRetry={() => {
        void refetchTask()
        if (hasReport) void refetchReport()
      }}
      isEmpty={!hasReport}
      emptyTitle="报告尚未生成"
      emptyDescription="报告将在执行阶段完成后生成。请先完成计划批准与执行流程。"
    >
      {task && hasReport && report && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold">调研报告</h1>
              <TaskStatusBadge status={task.status} />
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handleRegenerate}
                disabled={regenerateMutation.isPending}
              >
                重新生成
              </Button>
              <Button
                variant="outline"
                onClick={handleExport}
                disabled={exportMutation.isPending}
              >
                导出 Markdown
              </Button>
              {task.status === 'REVIEW_REQUIRED' && (
                <Button
                  onClick={handleConfirm}
                  disabled={confirmMutation.isPending}
                >
                  确认报告
                </Button>
              )}
            </div>
          </div>

          {report.pending_warnings.length > 0 && (
            <Card className="border-amber-300 bg-amber-50">
              <CardContent className="pt-4">
                <p className="mb-2 font-medium text-amber-900">
                  关键待定项警告
                </p>
                <ul className="list-inside list-disc text-sm text-amber-900">
                  {report.pending_warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {report.sections.map((section) => (
            <Card key={section.key}>
              <CardContent className="space-y-4 pt-6">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold">{section.title}</h2>
                  {section.is_pending && (
                    <ClaimLabel label="pending" />
                  )}
                </div>

                <SafeMarkdown markdown={section.markdown} />

                {section.claims.length > 0 && (
                  <div className="space-y-2 border-t pt-4">
                    <p className="text-sm font-medium text-muted-foreground">
                      论断标签
                    </p>
                    <ul className="space-y-2">
                      {section.claims.map((claim: ReportClaim) => (
                        <li
                          key={claim.id}
                          className="flex flex-wrap items-start gap-2 text-sm"
                        >
                          <ClaimLabel label={claim.label} />
                          <span className="flex-1">{claim.claim}</span>
                          {claim.evidence_ids.map((eid) => (
                            <button
                              key={eid}
                              type="button"
                              className="text-xs text-blue-600 underline hover:text-blue-800"
                              onClick={() => scrollToEvidence(eid)}
                            >
                              {eid.slice(0, 8)}
                            </button>
                          ))}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}

          <div id="evidence-index" className="text-xs text-muted-foreground">
            生成时间：{new Date(report.generated_at).toLocaleString()}
          </div>
        </div>
      )}
    </QueryState>
  )
}
