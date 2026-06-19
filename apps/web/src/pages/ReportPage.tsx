import { useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileDown,
  FileText,
  HelpCircle,
  Lightbulb,
  RefreshCw,
} from 'lucide-react'
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
import { ClaimLabel } from '@/components/common/ClaimLabel'
import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import {
  PageLayout,
  PrimaryWorkArea,
  SupportingPanel,
  SecondaryNavigation,
} from '@/components/common/InfoHierarchy'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { QueryState } from '@/components/common/QueryState'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { StatusGuide } from '@/components/common/StatusGuide'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { MetricChip } from '@/components/common/visual'
import { Card, CardContent } from '@/components/ui/card'
import { buildEvidenceLookup, getEvidenceLabel } from '@/lib/evidenceIndex'
import { cn } from '@/lib/utils'
import { CLAIM_LABEL_COPY, CTA_COPY, PAGE_GUIDE_COPY } from '@/lib/uiCopy'
import type { ReportClaim, ReportSection } from '@/types/report'

const LABEL_ICON: Record<string, ReactNode> = {
  fact: <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />,
  inference: <BookOpen className="h-4 w-4 text-blue-600" aria-hidden />,
  recommendation: <Lightbulb className="h-4 w-4 text-violet-600" aria-hidden />,
  pending: <HelpCircle className="h-4 w-4 text-amber-600" aria-hidden />,
}

function isWeakClaim(claim: ReportClaim): boolean {
  return claim.label === 'pending' || claim.requires_user_review === true
}

function sectionPath(taskId: string | undefined, sectionKey: string) {
  return `/tasks/${taskId}/report/sections/${sectionKey}`
}

export function ReportPage() {
  const { taskId, sectionKey } = useParams<{ taskId: string; sectionKey?: string }>()
  const location = useLocation()
  const viewMode = sectionKey
    ? 'section'
    : location.pathname.endsWith('/report/full')
      ? 'full'
      : 'summary'

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

  const { data: evidence } = useEvidence(taskId, Boolean(taskId) && Boolean(report))

  const confirmMutation = useConfirmReport()
  const exportMutation = useExportReport()
  const generateMutation = useGenerateReport()
  const regenerateMutation = useRegenerateReport()

  const evidenceLookup = useMemo(() => buildEvidenceLookup(evidence), [evidence])

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
    const allClaims = report.sections.flatMap((s) => s.claims)
    const allEvidenceIds = allClaims.flatMap((c) => c.evidence_ids)
    const uniqueEvidenceIds = [...new Set(allEvidenceIds)]
    const claimsByLabel: Record<string, ReportClaim[]> = {}

    for (const claim of allClaims) {
      ;(claimsByLabel[claim.label] ??= []).push(claim)
    }

    return {
      repoCount: task?.repo_urls?.length ?? 0,
      sectionCount: report.sections.length,
      evidenceTotal: uniqueEvidenceIds.length,
      claimTotal: allClaims.length,
      pendingCount: claimsByLabel.pending?.length ?? 0,
      allClaims,
      uniqueEvidenceIds,
      claimsByLabel,
      weakClaims: allClaims.filter(isWeakClaim),
    }
  }, [report, task])

  const selectedSection = report?.sections.find((section) => section.key === sectionKey)
  const selectedIndex = report?.sections.findIndex((section) => section.key === sectionKey) ?? -1
  const guide = PAGE_GUIDE_COPY.report
  const isLoading = taskLoading || (hasReport && reportLoading)
  const isError = taskError || (reportError && !reportNotFound)
  const error = taskErr ?? reportErr
  const shouldShowGenerate = task && (!hasReport || reportNotFound || !report)

  const renderEvidenceRefs = (evidenceIds: string[]) => {
    if (evidenceIds.length === 0) return null
    return (
      <div className="mt-2 flex flex-wrap gap-1.5">
        {evidenceIds.map((id) => {
          const item = evidenceLookup.byId.get(id)
          const label = getEvidenceLabel(id, evidenceLookup)
          if (!item) {
            return (
              <span
                key={id}
                className="rounded-md border border-dashed px-2 py-0.5 text-xs text-muted-foreground"
                title={id}
              >
                {label}
              </span>
            )
          }
          return (
            <button
              key={id}
              type="button"
              onClick={() => scrollToEvidence(id)}
              className="rounded-md border bg-muted px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-700"
              title={item.quote_or_summary}
            >
              {label}
            </button>
          )
        })}
      </div>
    )
  }

  const renderClaims = (claims: ReportClaim[]) => {
    if (claims.length === 0) {
      return <p className="text-sm text-muted-foreground">暂无结论</p>
    }

    return (
      <ul className="space-y-3">
        {claims.map((claim) => {
          const weak = isWeakClaim(claim)
          return (
            <li
              key={claim.id}
              className={cn(
                'rounded-md border p-3 text-sm',
                weak ? 'border-amber-300 bg-amber-50' : 'bg-background',
              )}
            >
              <div className="flex flex-wrap items-start gap-2">
                <ClaimLabel label={claim.label} />
                <span className="min-w-0 flex-1">{claim.claim}</span>
                {weak && (
                  <span className="text-xs text-amber-700">
                    <AlertTriangle className="mr-0.5 inline h-3 w-3" aria-hidden />
                    需进一步验证
                  </span>
                )}
              </div>
              {renderEvidenceRefs(claim.evidence_ids)}
            </li>
          )
        })}
      </ul>
    )
  }

  const renderOverview = () => {
    if (!summaryData || !report) return null

    return (
      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-muted-foreground" aria-hidden />
              <h2 className="text-lg font-semibold">报告概要</h2>
            </div>
            <p className="text-sm text-muted-foreground">调研目标：{task?.goal}</p>
            <div className="flex flex-wrap gap-2">
              <MetricChip label="仓库" value={summaryData.repoCount} />
              <MetricChip label="证据" value={summaryData.evidenceTotal} tone="green" />
              <MetricChip label="结论" value={summaryData.claimTotal} tone="violet" />
              <MetricChip label="章节" value={summaryData.sectionCount} tone="slate" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3 pt-6">
            <h2 className="text-lg font-semibold">阅读入口</h2>
            <div className="grid gap-3 md:grid-cols-2">
              <Link
                to={`/tasks/${taskId}/report/full`}
                className="rounded-lg border bg-muted/25 p-4 transition-colors hover:border-blue-300 hover:bg-blue-50"
              >
                <p className="font-medium">完整报告预览</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  连续阅读完整 Markdown，不再按章节切成卡片。
                </p>
              </Link>
              <div className="rounded-lg border p-4">
                <p className="font-medium">按章节阅读</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {report.sections.slice(0, 6).map((section) => (
                    <Link
                      key={section.key}
                      to={sectionPath(taskId, section.key)}
                      className="rounded-md border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-blue-300 hover:text-blue-700"
                    >
                      {section.title}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {(report.pending_warnings.length > 0 || summaryData.weakClaims.length > 0) && (
          <Card className="border-amber-300 bg-amber-50">
            <CardContent className="space-y-3 pt-6">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" aria-hidden />
                <h2 className="text-lg font-semibold text-amber-900">风险提醒</h2>
              </div>
              {report.pending_warnings.length > 0 && (
                <ul className="list-inside list-disc text-sm text-amber-900">
                  {report.pending_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              )}
              {summaryData.weakClaims.length > 0 && (
                <p className="text-sm text-amber-800">
                  有 {summaryData.weakClaims.length} 条结论证据较弱或需要人工确认。
                </p>
              )}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent className="space-y-4 pt-6">
            <h2 className="text-lg font-semibold">关键结论</h2>
            {(['fact', 'inference', 'recommendation', 'pending'] as const).map((label) => {
              const claims = summaryData.claimsByLabel[label] ?? []
              if (claims.length === 0) return null
              const copy = CLAIM_LABEL_COPY[label]
              return (
                <section key={label} className="space-y-2">
                  <div className="flex items-center gap-2">
                    {LABEL_ICON[label]}
                    <h3 className="text-sm font-medium">
                      {copy.label}（{claims.length}）
                    </h3>
                  </div>
                  {renderClaims(claims)}
                </section>
              )
            })}
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderFullReport = () => {
    if (!report) return null
    return (
      <div className="space-y-4">
        {report.pending_warnings.length > 0 && (
          <Card className="border-amber-300 bg-amber-50">
            <CardContent className="pt-4">
              <p className="mb-2 font-medium text-amber-900">关键待定项警告</p>
              <ul className="list-inside list-disc text-sm text-amber-900">
                {report.pending_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardContent className="pt-6">
            <SafeMarkdown markdown={report.markdown} />
          </CardContent>
        </Card>
      </div>
    )
  }

  const renderSection = (section: ReportSection | undefined) => {
    if (!section || !report) {
      return (
        <Card>
          <CardContent className="space-y-2 pt-6">
            <h2 className="text-lg font-semibold">章节不存在</h2>
            <p className="text-sm text-muted-foreground">请选择右侧目录中的报告章节。</p>
          </CardContent>
        </Card>
      )
    }

    const prev = selectedIndex > 0 ? report.sections[selectedIndex - 1] : null
    const next =
      selectedIndex >= 0 && selectedIndex < report.sections.length - 1
        ? report.sections[selectedIndex + 1]
        : null

    return (
      <div className="space-y-4">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold">{section.title}</h2>
              {section.is_pending && <ClaimLabel label="pending" />}
            </div>
            <SafeMarkdown markdown={section.markdown} />
            {section.claims.length > 0 && (
              <div className="border-t pt-4">
                <p className="mb-3 text-sm font-medium text-muted-foreground">结论与证据</p>
                {renderClaims(section.claims)}
              </div>
            )}
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
          ) : <span />}
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

  const renderMain = () => {
    if (viewMode === 'full') return renderFullReport()
    if (viewMode === 'section') return renderSection(selectedSection)
    return renderOverview()
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
            { label: CTA_COPY.viewWorkflow, href: `/tasks/${taskId}/workflow` },
            { label: '查看对比', href: `/tasks/${taskId}/comparison` },
          ]}
          backTo={{ label: CTA_COPY.backToHistory, href: '/history' }}
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
      {task && hasReport && report && (
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
                ? { label: CTA_COPY.confirm, onClick: handleConfirm }
                : { label: CTA_COPY.export, onClick: handleExport }
            }
            statusBadge={<TaskStatusBadge status={task.status} />}
          />

          <PageLayout
            ratio="3:1"
            supporting={
              <div className="space-y-4">
                <SupportingPanel title="报告导航">
                  <div className="space-y-2">
                    <Link
                      to={`/tasks/${taskId}/report`}
                      className={cn(
                        'block rounded-md px-2 py-1.5 text-sm hover:bg-muted',
                        viewMode === 'summary' && 'bg-primary/10 text-primary',
                      )}
                    >
                      报告概要
                    </Link>
                    <Link
                      to={`/tasks/${taskId}/report/full`}
                      className={cn(
                        'block rounded-md px-2 py-1.5 text-sm hover:bg-muted',
                        viewMode === 'full' && 'bg-primary/10 text-primary',
                      )}
                    >
                      完整报告预览
                    </Link>
                    <div className="border-t pt-2">
                      {report.sections.map((section, index) => (
                        <Link
                          key={section.key}
                          to={sectionPath(taskId, section.key)}
                          className={cn(
                            'block rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground',
                            section.key === sectionKey && 'bg-primary/10 text-primary',
                          )}
                        >
                          {index + 1}. {section.title}
                        </Link>
                      ))}
                    </div>
                  </div>
                </SupportingPanel>
                <SupportingPanel title="证据索引">
                  <EvidenceSummary
                    evidenceIds={summaryData?.uniqueEvidenceIds ?? []}
                    evidenceItems={evidence}
                    defaultExpanded
                    onViewDetail={scrollToEvidence}
                  />
                </SupportingPanel>
                <SupportingPanel title="报告信息">
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <div>生成时间：{new Date(report.generated_at).toLocaleString()}</div>
                    <div>{summaryData?.sectionCount ?? 0} 个章节</div>
                    <div>{summaryData?.evidenceTotal ?? 0} 条证据</div>
                    <div>{summaryData?.claimTotal ?? 0} 条结论</div>
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
            title={viewMode === 'section' ? selectedSection?.title : '报告操作'}
            description="导出会保留 Markdown、结论标签与证据引用。"
            secondary={[
              ...(task.status === 'REVIEW_REQUIRED'
                ? [
                    {
                      label: CTA_COPY.export,
                      onClick: handleExport,
                      icon: <FileDown className="h-4 w-4" aria-hidden />,
                    },
                  ]
                : []),
              {
                label: CTA_COPY.regenerate,
                onClick: handleRegenerate,
                icon: <RefreshCw className="h-4 w-4" aria-hidden />,
                disabled: regenerateMutation.isPending,
              },
              { label: '报告概要', href: `/tasks/${taskId}/report` },
              { label: '完整预览', href: `/tasks/${taskId}/report/full` },
            ]}
          />

          <SecondaryNavigation
            items={[
              { label: CTA_COPY.viewWorkflow, href: `/tasks/${taskId}/workflow` },
              { label: '查看对比', href: `/tasks/${taskId}/comparison` },
            ]}
            backTo={{ label: CTA_COPY.backToHistory, href: '/history' }}
          />
        </div>
      )}
    </QueryState>
  )
}
