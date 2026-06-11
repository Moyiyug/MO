import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { useComparison, useRecomputeWeights } from '@/api/comparison'
import { useTask } from '@/api/tasks'
import { ClaimLabel } from '@/components/common/ClaimLabel'
import { QueryState } from '@/components/common/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { DimensionScore } from '@/types/comparison'

const WEIGHT_LABELS: Record<string, string> = {
  reproducibility: '可复现性',
  documentation: '文档完整度',
  research_value: '研究价值',
  engineering_fit: '工程契合度',
  extensibility: '可扩展性',
}

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

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError && !isNotFound}
      error={error}
      onRetry={() => void refetch()}
      isEmpty={!canShow || isNotFound}
      emptyTitle="对比尚未生成"
      emptyDescription="对比矩阵将在执行阶段 comparison_builder 节点完成后可用。"
    >
      {matrix && (
        <div className="space-y-6">
          <h1 className="text-2xl font-semibold">多仓库对比</h1>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="text-lg font-semibold">加权排名</h2>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                {matrix.rankings.map((r) => (
                  <li key={r.repo_url}>
                    <span className="font-medium">{r.repo_name}</span>
                    <span className="text-muted-foreground">
                      {' '}
                      — {r.weighted_total.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

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
                    {matrix.dimensions.map((dim) => (
                      <tr key={dim} className="border-b">
                        <td className="p-2 font-medium">{dim}</td>
                        {matrix.repo_urls.map((url) => {
                          const score = scoresByRepo
                            .get(url)
                            ?.find((s) => s.dimension === dim)
                          return (
                            <td key={url} className="p-2">
                              {score ? (
                                <div>
                                  <span className="font-mono">
                                    {score.score.toFixed(2)}
                                  </span>
                                  <ClaimLabel
                                    label={score.label}
                                    className="ml-1"
                                  />
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {score.rationale.slice(0, 60)}
                                  </p>
                                </div>
                              ) : (
                                '—'
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="text-lg font-semibold">权重编辑</h2>
              <p className="text-sm text-muted-foreground">
                出报告前可调整权重并重新加权（不重跑 LLM）。当前总和：
                {weightSum.toFixed(2)}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(activeWeights).map(([key, val]) => (
                  <div key={key} className="space-y-1">
                    <Label htmlFor={`w-${key}`}>
                      {WEIGHT_LABELS[key] ?? key}
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
              </div>
              <Button
                onClick={handleRecompute}
                disabled={recompute.isPending}
              >
                应用权重并重算
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-4 pt-6">
              <h2 className="text-lg font-semibold">场景推荐</h2>
              <p className="text-sm">{matrix.recommendation}</p>
              {matrix.recommendation_evidence_ids.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  证据：
                  {matrix.recommendation_evidence_ids
                    .map((id) => id.slice(0, 8))
                    .join(', ')}
                </p>
              )}
            </CardContent>
          </Card>

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
        </div>
      )}
    </QueryState>
  )
}
