import { useCallback, useMemo } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { FileDown, FileText, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { MOError } from '@/api/client'
import { useEvidence } from '@/api/evidence'
import {
  useConfirmReport,
  useExportReport,
  useGenerateReport,
  useRegenerateReport,
  useReport,
} from '@/api/report'
import { useTask } from '@/api/tasks'
import {
  PageLayout,
  PrimaryWorkArea,
  SupportingPanel,
  SecondaryNavigation,
} from '@/components/common/InfoHierarchy'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { QueryState } from '@/components/common/QueryState'
import { StatusGuide } from '@/components/common/StatusGuide'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'
import { ReportDataOverview } from '@/features/report/components/ReportDataOverview'
import { ReportEvidenceView } from '@/features/report/components/ReportEvidenceView'
import { ReportNavigationPanel } from '@/features/report/components/ReportNavigationPanel'
import { ReportReaderFull } from '@/features/report/components/ReportReaderFull'
import { ReportReaderOverview } from '@/features/report/components/ReportReaderOverview'
import { ReportReaderSection } from '@/features/report/components/ReportReaderSection'
import { ReportSectionDataView } from '@/features/report/components/ReportSectionDataView'
import {
  collectReportEvidenceIds,
  getReportViewMode,
  type ReportViewMode,
} from '@/features/report/components/reportViewUtils'
import { buildEvidenceLookup } from '@/lib/evidenceIndex'
import { CTA_COPY, PAGE_GUIDE_COPY, REPORT_VIEW_COPY } from '@/lib/uiCopy'
import type { ReportClaim } from '@/types/report'

function isWeakClaim(claim: ReportClaim): boolean {
  return claim.label === 'pending' || claim.requires_user_review === true
}

function viewTitle(viewMode: ReportViewMode, sectionTitle?: string) {
  if (viewMode === 'reader-section') return sectionTitle ?? REPORT_VIEW_COPY.readerSection.label
  if (viewMode === 'data-section') return sectionTitle ? `${sectionTitle}：数据` : REPORT_VIEW_COPY.dataOverview.label
  if (viewMode === 'reader-full') return REPORT_VIEW_COPY.readerFull.label
  if (viewMode === 'data-overview') return REPORT_VIEW_COPY.dataOverview.label
  if (viewMode === 'evidence') return REPORT_VIEW_COPY.evidence.label
  return REPORT_VIEW_COPY.readerSummary.label
}

export function ReportPage() {
  const { taskId, sectionKey } = useParams<{
    taskId: string
    sectionKey?: string
  }>()
  const location = useLocation()
  const viewMode = getReportViewMode(location.pathname, sectionKey)

  const {
    data: task,
    isLoading: taskLoading,
    isError: taskError,
    error: taskErr,
    refetch: refetchTask,
  } = useTask(taskId)

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
  } = useReport(taskId, hasReport, { retry: false })

  const reportNotFound =
    reportError && reportErr instanceof MOError && reportErr.status === 404

  const shouldFetchEvidence =
    Boolean(taskId) &&
    Boolean(report) &&
    (viewMode === 'data-section' || viewMode === 'evidence')
  const { data: evidence } = useEvidence(taskId, shouldFetchEvidence)
  const evidenceLookup = useMemo(() => buildEvidenceLookup(evidence), [evidence])

  const confirmMutation = useConfirmReport()
  const exportMutation = useExportReport()
  const generateMutation = useGenerateReport()
  const regenerateMutation = useRegenerateReport()

  const scrollToEvidence = useCallback((evidenceId: string) => {
    const el = document.getElementById(`evidence-${evidenceId}`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [])

  const handleExport = () => {
    if (!taskId) return
    exportMutation.mutate(taskId, {
      onSuccess: () => toast.success('报告已导出'),
      onError: (e) => toast.error(e instanceof Error ? e.message : '导出失败'),
    })
  }

  const handleGenerate = () => {
    if (!taskId) return
    generateMutation.mutate(taskId, {
      onSuccess: () => toast.success('报告已生成'),
      onError: (e) => toast.error(e instanceof Error ? e.message : '生成报告失败'),
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

  const summaryData = useMemo(() => {
    if (!report) return null
    const allClaims = report.sections.flatMap((section) => section.claims)
    return {
      repoCount: task?.repo_urls?.length ?? 0,
      sectionCount: report.sections.length,
      claimTotal: allClaims.length,
      pendingCount: allClaims.filter((claim) => claim.label === 'pending').length,
      weakClaimCount: allClaims.filter(isWeakClaim).length,
      uniqueEvidenceIds: collectReportEvidenceIds(report),
    }
  }, [report, task])

  const selectedSection = report?.sections.find(
    (section) => section.key === sectionKey,
  )
  const selectedIndex =
    report?.sections.findIndex((section) => section.key === sectionKey) ?? -1
  const prevSection =
    report && selectedIndex > 0 ? report.sections[selectedIndex - 1] : null
  const nextSection =
    report && selectedIndex >= 0 && selectedIndex < report.sections.length - 1
      ? report.sections[selectedIndex + 1]
      : null

  const guide = PAGE_GUIDE_COPY.report
  const isLoading = taskLoading || (hasReport && reportLoading)
  const isError = taskError || (reportError && !reportNotFound)
  const error = taskErr ?? reportErr
  const shouldShowGenerate = task && (!hasReport || reportNotFound || !report)

  const renderMain = () => {
    if (!taskId || !report) return null

    switch (viewMode) {
      case 'reader-full':
        return <ReportReaderFull report={report} />
      case 'reader-section':
        return (
          <ReportReaderSection
            taskId={taskId}
            section={selectedSection}
            prev={prevSection}
            next={nextSection}
          />
        )
      case 'data-overview':
        return <ReportDataOverview taskId={taskId} report={report} />
      case 'data-section':
        return (
          <ReportSectionDataView
            section={selectedSection}
            evidenceItems={evidence}
            evidenceLookup={evidenceLookup}
            onViewEvidence={scrollToEvidence}
          />
        )
      case 'evidence':
        return (
          <ReportEvidenceView
            report={report}
            evidenceItems={evidence}
            allEvidenceIds={summaryData?.uniqueEvidenceIds ?? []}
            evidenceLookup={evidenceLookup}
            onViewDetail={scrollToEvidence}
          />
        )
      case 'reader-summary':
      default:
        return (
          <ReportReaderOverview
            taskId={taskId}
            taskGoal={task?.goal}
            report={report}
            repoCount={summaryData?.repoCount ?? 0}
            pendingCount={summaryData?.pendingCount ?? 0}
            weakClaimCount={summaryData?.weakClaimCount ?? 0}
          />
        )
    }
  }

  const renderMissingReport = () => {
    if (!task) return null
    return (
      <div className="mo-page-shell">
        <StatusGuide
          title={guide.title}
          whatNow={guide.whatNow}
          blockReason={guide.notGenerated}
          severity="warning"
          primaryAction={{
            label: generateMutation.isPending ? '生成中…' : '生成报告',
            onClick: handleGenerate,
            disabled: generateMutation.isPending,
          }}
          statusBadge={<TaskStatusBadge status={task.status} />}
        />

        <Card>
          <CardContent className="space-y-3 pt-6">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" aria-hidden />
              <h2 className="text-lg font-semibold">报告尚未生成</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              GET /report 只读取已有报告。需要报告时请显式点击生成，生成后再审阅、导出或确认。
            </p>
          </CardContent>
        </Card>

        <SecondaryNavigation
          items={[
            { label: CTA_COPY.viewWorkflow, to: `/tasks/${taskId}/workflow` },
            { label: '查看对比', to: `/tasks/${taskId}/comparison` },
          ]}
          backTo={{ label: CTA_COPY.backToHistory, to: '/history' }}
        />
      </div>
    )
  }

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError}
      error={error}
      onRetry={() => {
        void refetchTask()
        if (hasReport) void refetchReport()
      }}
      isEmpty={!task}
      emptyTitle="任务不存在"
      emptyDescription="请返回历史列表重新选择任务。"
    >
      {shouldShowGenerate && renderMissingReport()}
      {task && hasReport && report && taskId && (
        <div className="mo-page-shell">
          <StatusGuide
            title={guide.title}
            whatNow={guide.whatNow}
            blockReason={
              report.pending_warnings.length > 0
                ? `有 ${report.pending_warnings.length} 个待定项需要关注`
                : task.status === 'REVIEW_REQUIRED'
                  ? '报告中有待确认的结论，请审阅后确认'
                  : undefined
            }
            severity={
              report.pending_warnings.length > 0 || task.status === 'REVIEW_REQUIRED'
                ? 'warning'
                : 'info'
            }
            primaryAction={
              task.status === 'REVIEW_REQUIRED'
                ? {
                    label: confirmMutation.isPending ? '确认中…' : CTA_COPY.confirm,
                    onClick: handleConfirm,
                    disabled: confirmMutation.isPending,
                  }
                : {
                    label: exportMutation.isPending ? '导出中…' : CTA_COPY.export,
                    onClick: handleExport,
                    disabled: exportMutation.isPending,
                  }
            }
            statusBadge={<TaskStatusBadge status={task.status} />}
          />

          <PageLayout
            ratio="3:1"
            supporting={
              <div className="space-y-4">
                <ReportNavigationPanel
                  taskId={taskId}
                  report={report}
                  viewMode={viewMode}
                  sectionKey={sectionKey}
                />
                <SupportingPanel title="报告信息">
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <div>版本：{report.report_version ?? 'unknown'}</div>
                    <div>生成时间：{new Date(report.generated_at).toLocaleString()}</div>
                    <div>{summaryData?.sectionCount ?? 0} 个章节</div>
                    <div>{summaryData?.claimTotal ?? 0} 条结论</div>
                    <div>
                      {(summaryData?.uniqueEvidenceIds.length ?? 0)} 条证据可在证据附录查看
                    </div>
                    {(summaryData?.pendingCount ?? 0) > 0 && (
                      <div className="font-medium text-amber-600">
                        {summaryData?.pendingCount} 条待确认
                      </div>
                    )}
                  </div>
                </SupportingPanel>
              </div>
            }
          >
            <PrimaryWorkArea>{renderMain()}</PrimaryWorkArea>
          </PageLayout>

          <PageCommandBar
            position="top"
            title={viewTitle(viewMode, selectedSection?.title)}
            description="导出会保留 Markdown、结论标签与证据引用。"
            secondary={[
              { label: REPORT_VIEW_COPY.readerSummary.label, to: `/tasks/${taskId}/report` },
              { label: REPORT_VIEW_COPY.readerFull.label, to: `/tasks/${taskId}/report/full` },
              { label: REPORT_VIEW_COPY.dataOverview.label, to: `/tasks/${taskId}/report/data` },
              { label: REPORT_VIEW_COPY.evidence.label, to: `/tasks/${taskId}/report/evidence` },
              ...(task.status === 'REVIEW_REQUIRED'
                ? [
                    {
                      label: CTA_COPY.export,
                      onClick: handleExport,
                      icon: <FileDown className="h-4 w-4" aria-hidden />,
                      disabled: exportMutation.isPending,
                    },
                  ]
                : []),
              {
                label: CTA_COPY.regenerate,
                onClick: handleRegenerate,
                icon: <RefreshCw className="h-4 w-4" aria-hidden />,
                disabled: regenerateMutation.isPending,
              },
            ]}
          />

          <SecondaryNavigation
            items={[
              { label: CTA_COPY.viewWorkflow, to: `/tasks/${taskId}/workflow` },
              { label: '查看对比', to: `/tasks/${taskId}/comparison` },
            ]}
            backTo={{ label: CTA_COPY.backToHistory, to: '/history' }}
          />
        </div>
      )}
    </QueryState>
  )
}
