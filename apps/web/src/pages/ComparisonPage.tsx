import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { useComparison, useRecomputeWeights } from '@/api/comparison'
import { useEvidence } from '@/api/evidence'
import { useTask } from '@/api/tasks'
import { ClaimLabel } from '@/components/common/ClaimLabel'
import { QueryState } from '@/components/common/QueryState'
import { StatusGuide } from '@/components/common/StatusGuide'
import {
  PageLayout,
  PrimaryWorkArea,
  SupportingPanel,
  SecondaryNavigation,
} from '@/components/common/InfoHierarchy'
import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PAGE_GUIDE_COPY, CTA_COPY, COMPARISON_DIMENSION_COPY } from '@/lib/uiCopy'
import type { DimensionScore } from '@/types/comparison'

/** P-005 Comparison — 对比矩阵 + 权重编辑 + 场景推荐 */
export function ComparisonPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task } = useTask(taskId)

  const canShow =
    task?.status === 'REPORT_DRAFT' ||
    task?.status === 'REVIEW_REQUIRED' ||
    task?.status === 'DONE'

  const {
    data: matrix,
    isLoading,
    isError,
    error,
    refetch,
  } = useComparison(taskId, canShow)
  const { data: evidence } = useEvidence(taskId, Boolean(taskId) && canShow)

  const isNotFound =
    isError && error instanceof Error && error.message.includes('not found')

  const recompute = useRecomputeWeights()
  const [weights, setWeights] = useState<Record<string, number> | null>(null)

  const activeWeights = weights ?? matrix?.weights ?? {}

  const weightSum = useMemo(
    () => Object.values(activeWeights).reduce((a, b) => a + b, 0),
    [activeWeights],
  )

  const scoresByRepo = useMemo(() => {
    if (!matrix) return new Map<string, DimensionScore[]>()
    const map = new Map<string, DimensionScore[]>()
    for (const s of matrix.scores) {
      const list = map.get(s.repo_url) ?? []
      list.push(s)
      map.set(s.repo_url, list)
    }
    return map
  }, [matrix])

  const handleWeightChange = (key: string, value: string) => {
    const num = parseFloat(value)
    if (Number.isNaN(num)) return
    setWeights({ ...activeWeights, [key]: num })
  }

  const handleRecompute = () => {
    if (!taskId) return
    if (Math.abs(weightSum - 1) > 0.01) {
      toast.error('权重之和须约等于 1.0')
      return
    }
    recompute.mutate(
      { taskId, payload: { weights: activeWeights } },
      {
        onSuccess: () => toast.success('权重已重算'),
        onError: (e) =>
          toast.error(e instanceof Error ? e.message : '重算失败'),
      },
    )
  }

  const guide = PAGE_GUIDE_COPY.comparison
  const weightIsValid = Math.abs(weightSum - 1) <= 0.01

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError && !isNotFound}
      error={error}
      onRetry={() => void refetch()}
      isEmpty={!canShow || isNotFound}
      emptyTitle="对比尚未生成"
      emptyDescription="对比矩阵将在执行阶段完成对比分析后可用。"
      emptyAction={{ label: '查看执行进度', href: `/tasks/${taskId}/workflow` }}
    >
      {matrix && (
        <div className="space-y-6 max-w-7xl mx-auto">
          <StatusGuide
            title={guide.title}
            whatNow={guide.whatNow}
            primaryAction={{ label: guide.primaryAction, href: `/tasks/${taskId}/report` }}
          />

          <PageCommandBar
            position="top"
            title="对比结果可重新加权"
            description={`当前权重总和 ${weightSum.toFixed(2)}，需等于 1.00 才能重算。`}
            primary={{ label: CTA_COPY.viewReport, href: `/tasks/${taskId}/report` }}
            secondary={[
              { label: CTA_COPY.viewWorkflow, href: `/tasks/${taskId}/workflow` },
              {
                label: recompute.isPending ? '重算中…' : '应用权重',
                onClick: handleRecompute,
                disabled: recompute.isPending || !weightIsValid,
              },
            ]}
          />

          <PageLayout ratio="3:1">
            <PrimaryWorkArea>
              {/* 加权排名 */}
              <Card>
                <CardContent className="space-y-4 pt-6">
                  <h2 className="text-lg font-semibold">加权排名</h2>
                  <ol className="space-y-3 text-sm">
                    {matrix.rankings.map((r, index) => (
                      <li key={r.repo_url} className="rounded-md border bg-muted/25 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium">
                            {index + 1}. {r.repo_name}
                          </span>
                          <span className="font-mono text-muted-foreground">
                            {r.weighted_total.toFixed(2)}
                          </span>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500"
                            style={{ width: `${Math.max(4, Math.min(100, r.weighted_total * 100))}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ol>
                </CardContent>
              </Card>

              {/* 对比矩阵 */}
              <Card>
                <CardContent className="space-y-4 pt-6">
                  <h2 className="text-lg font-semibold">对比矩阵</h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="border-b">
                          <th className="p-2 text-left">维度</th>
                          {matrix.repo_urls.map((url) => (
                            <th key={url} className="p-2 text-left">
                              {url.split('/').pop()}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {matrix.dimensions.map((dim) => {
                          const dimCopy = COMPARISON_DIMENSION_COPY[dim]
                          return (
                          <tr key={dim} className="border-b">
                            <td className="p-2 align-top">
                              <p className="font-medium">{dimCopy?.label ?? dim}</p>
                              {dimCopy?.description && (
                                <p className="mt-1 max-w-48 text-xs text-muted-foreground">
                                  {dimCopy.description}
                                </p>
                              )}
                            </td>
                            {matrix.repo_urls.map((url) => {
                              const score = scoresByRepo
                                .get(url)
                                ?.find((s) => s.dimension === dim)
                              return (
                                <td key={url} className="min-w-56 p-2 align-top">
                                  {score ? (
                                    <div className="space-y-2">
                                      <div className="flex items-center gap-2">
                                        <span className="font-mono">
                                          {score.score.toFixed(2)}
                                        </span>
                                        <ClaimLabel label={score.label} />
                                      </div>
                                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                                        <div
                                          className="h-full rounded-full bg-blue-500"
                                          style={{ width: `${Math.max(4, Math.min(100, score.score * 100))}%` }}
                                        />
                                      </div>
                                      <p
                                        className="text-xs text-muted-foreground mt-1"
                                        title={score.rationale}
                                      >
                                        {score.rationale.slice(0, 60)}
                                        {score.rationale.length > 60 ? '…' : ''}
                                      </p>
                                    </div>
                                  ) : (
                                    '—'
                                  )}
                                </td>
                              )
                            })}
                          </tr>
                        )})}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* 场景推荐 */}
              <Card>
                <CardContent className="space-y-4 pt-6">
                  <h2 className="text-lg font-semibold">场景推荐</h2>
                  <p className="text-sm">{matrix.recommendation}</p>
                  {matrix.recommendation_evidence_ids.length > 0 && (
                    <EvidenceSummary
                      evidenceIds={matrix.recommendation_evidence_ids}
                      evidenceItems={evidence}
                      defaultExpanded
                    />
                  )}
                </CardContent>
              </Card>

              {/* 局限 */}
              {matrix.limitations.length > 0 && (
                <Card className="border-amber-300 bg-amber-50">
                  <CardContent className="space-y-2 pt-6">
                    <h2 className="text-lg font-semibold text-amber-900">局限</h2>
                    <ul className="list-inside list-disc text-sm text-amber-900">
                      {matrix.limitations.map((lim) => (
                        <li key={lim}>{lim}</li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
            </PrimaryWorkArea>

            {/* 辅助面板：权重编辑 */}
            <SupportingPanel title="权重编辑" variant="card">
              <p className="text-xs text-muted-foreground mb-3">
                出报告前可调整权重并重新加权。当前总和：{weightSum.toFixed(2)}
              </p>
              <div className="mb-3 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={weightIsValid ? 'h-full rounded-full bg-emerald-500' : 'h-full rounded-full bg-amber-500'}
                  style={{ width: `${Math.max(4, Math.min(100, weightSum * 100))}%` }}
                />
              </div>
              {!weightIsValid && (
                <p className="mb-3 rounded-md bg-amber-50 p-2 text-xs text-amber-800">
                  权重总和需要等于 1.00 后才能重算。
                </p>
              )}
              <div className="space-y-3">
                {Object.entries(activeWeights).map(([key, val]) => (
                  <div key={key} className="space-y-1">
                    <Label htmlFor={`w-${key}`} className="text-xs">
                      {COMPARISON_DIMENSION_COPY[key]?.label ?? key}
                    </Label>
                    <Input
                      id={`w-${key}`}
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={val}
                      onChange={(e) => handleWeightChange(key, e.target.value)}
                    />
                  </div>
                ))}
                <Button
                  size="sm"
                  onClick={handleRecompute}
                  disabled={recompute.isPending || !weightIsValid}
                >
                  应用权重并重算
                </Button>
              </div>
            </SupportingPanel>
          </PageLayout>

          <SecondaryNavigation
            items={[
              { label: CTA_COPY.viewWorkflow, href: `/tasks/${taskId}/workflow` },
              { label: CTA_COPY.viewReport, href: `/tasks/${taskId}/report` },
            ]}
            backTo={{ label: CTA_COPY.backToHistory, href: '/history' }}
          />
        </div>
      )}
    </QueryState>
  )
}
