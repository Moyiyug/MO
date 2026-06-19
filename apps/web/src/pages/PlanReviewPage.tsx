import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'

import {
  useApprovePlan,
  useGeneratePlan,
  usePlan,
  useReplan,
  useSubmitClarifications,
  useTask,
} from '@/api/tasks'
import { useSelectRepoCandidates, useRepoCandidates } from '@/api/repoDiscovery'
import { QueryState } from '@/components/common/QueryState'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { StatusGuide } from '@/components/common/StatusGuide'
import {
  PageLayout,
  PrimaryWorkArea,
  SupportingPanel,
  SecondaryNavigation,
} from '@/components/common/InfoHierarchy'
import { SectionTabs } from '@/components/common/SectionTabs'
import { NextActionBar } from '@/components/common/NextActionBar'
import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { WAITING_USER_TASK_STATUSES } from '@/types/enums'
import { isRubricValid } from '@/types/plan'
import {
  unansweredRequired,
  usePlanDraftStore,
} from '@/stores/planDraftStore'
import { cn } from '@/lib/utils'
import {
  PAGE_GUIDE_COPY,
  STEP_TOOL_COPY,
  RISK_LEVEL_COPY,
  CTA_COPY,
} from '@/lib/uiCopy'

/** P-002 PlanReview — 调研计划审阅 */
export function PlanReviewPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()

  const taskQuery = useTask(taskId)
  const planQuery = usePlan(taskId)
  const generatePlan = useGeneratePlan()
  const approvePlan = useApprovePlan()
  const replan = useReplan()
  const submitClarifications = useSubmitClarifications()
  const selectCandidates = useSelectRepoCandidates()
  const repoCandidatesQuery = useRepoCandidates(taskId)

  const {
    rubricWeights,
    disabledStepIds,
    clarificationAnswers,
    initFromPlan,
    setRubricWeight,
    toggleStep,
    setClarificationAnswer,
  } = usePlanDraftStore()

  const [confirmApprove, setConfirmApprove] = useState(false)
  const [confirmReplan, setConfirmReplan] = useState(false)
  const [replanReason, setReplanReason] = useState('')
  const [selectedRepoUrls, setSelectedRepoUrls] = useState<string[]>([])
  const [syncedPlanId, setSyncedPlanId] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState('steps')

  const task = taskQuery.data
  const plan = planQuery.data

  useEffect(() => {
    if (!plan) return
    initFromPlan(plan)
    // 计划变化时用服务端的选中状态重置本地草稿
    if (plan.id !== syncedPlanId) {
      setSyncedPlanId(plan.id)
      setSelectedRepoUrls(
        plan.repo_candidates.filter((c) => c.selected).map((c) => c.repo_url),
      )
    }
  }, [plan, initFromPlan, syncedPlanId])

  const isWaitingUser =
    task && WAITING_USER_TASK_STATUSES.includes(task.status)
  const needsClarification = task?.status === 'WAITING_USER_CLARIFICATION'
  const needsApproval = task?.status === 'WAITING_USER_APPROVAL'
  const isExecuting = task?.status === 'EXECUTING'
  const isApproved =
    task?.status === 'PLAN_APPROVED' || isExecuting
  const isFailed = task?.status === 'FAILED'
  const isPostReport =
    task?.status === 'REVIEW_REQUIRED' ||
    task?.status === 'REPORT_DRAFT' ||
    task?.status === 'DONE'
  const canRegeneratePlan = !isExecuting && !generatePlan.isPending
  const canReplan =
    task?.status === 'WAITING_USER_APPROVAL' ||
    task?.status === 'PLAN_APPROVED' ||
    isExecuting ||
    isFailed ||
    isPostReport

  const missingClarifications = plan
    ? unansweredRequired(plan.clarifying_questions, clarificationAnswers)
    : []

  const rubricValid = isRubricValid(rubricWeights)

  const candidates = repoCandidatesQuery.data?.candidates ?? plan?.repo_candidates ?? []
  const discoveryNote = repoCandidatesQuery.data?.discovery_note ?? null
  const hasCandidates = candidates.length > 0
  const noRepoSelected = (task?.repo_urls?.length ?? 0) === 0
  const selectionValid =
    selectedRepoUrls.length >= 1 && selectedRepoUrls.length <= 5

  // ── StatusGuide 推导 ───────────────────────────────────────
  const guide = PAGE_GUIDE_COPY.planReview
  let blockReason: string | undefined
  if (isWaitingUser && noRepoSelected) {
    blockReason = guide.blockReasons.noRepoSelected
  } else if (isWaitingUser && missingClarifications.length > 0) {
    blockReason = guide.blockReasons.unansweredRequired
  } else if (needsApproval) {
    blockReason = guide.blockReasons.waitingApproval
  }

  const primaryAction = !blockReason && needsApproval
    ? { label: CTA_COPY.approve, onClick: () => setConfirmApprove(true) }
    : !blockReason && needsClarification
      ? { label: '提交澄清', onClick: handleSubmitClarifications }
      : !blockReason && isApproved
        ? { label: '查看工作流', href: `/tasks/${taskId}/workflow` }
        : undefined

  // ── helpers ────────────────────────────────────────────────
  const toggleRepo = (url: string) => {
    setSelectedRepoUrls((prev) =>
      prev.includes(url) ? prev.filter((u) => u !== url) : [...prev, url],
    )
  }

  async function handleConfirmSelection() {
    if (!taskId) return
    if (!selectionValid) {
      toast.error('请选择 1–5 个仓库作为调研对象')
      return
    }
    try {
      await selectCandidates.mutateAsync({
        taskId,
        payload: { selected_repo_urls: selectedRepoUrls },
      })
      toast.success('已确认调研仓库')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '确认失败')
    }
  }

  async function handleSubmitClarifications() {
    if (!taskId || !plan) return
    if (missingClarifications.length > 0) {
      toast.error('请回答所有必填澄清问题')
      return
    }
    try {
      await submitClarifications.mutateAsync({
        taskId,
        payload: {
          answers: Object.entries(clarificationAnswers).map(
            ([question_id, answer]) => ({ question_id, answer }),
          ),
        },
      })
      toast.success('澄清已提交')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '提交失败')
    }
  }

  async function handleApprove() {
    if (!taskId) return
    if (!rubricValid) {
      toast.error('评分权重之和必须约等于 1.0')
      return
    }
    if (noRepoSelected) {
      toast.error('请先在候选清单中选择至少一个调研仓库')
      return
    }
    try {
      await approvePlan.mutateAsync({
        taskId,
        payload: {
          rubric_weights: rubricWeights,
          disabled_step_ids: Array.from(disabledStepIds),
        },
      })
      toast.success('计划已批准')
      setConfirmApprove(false)
      navigate(`/tasks/${taskId}/workflow`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批准失败')
    }
  }

  async function handleReplan() {
    if (!taskId) return
    if (!canReplan) {
      toast.error('当前状态不支持重规划')
      return
    }
    try {
      await replan.mutateAsync({
        taskId,
        payload: { reason: replanReason || null },
      })
      toast.success('已触发重规划')
      setConfirmReplan(false)
      setReplanReason('')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '重规划失败')
    }
  }

  async function handleRegenerate() {
    if (!taskId) return
    try {
      await generatePlan.mutateAsync(taskId)
      toast.success('计划已重新生成')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败')
    }
  }

  // ── SectionTabs 定义 ────────────────────────────────────────
  const sectionTabs = [
    { id: 'steps', label: '计划步骤', count: plan?.proposed_steps.length },
  ]
  if (hasCandidates) {
    sectionTabs.push({ id: 'repos', label: '候选仓库', count: candidates.length })
  }
  sectionTabs.push({ id: 'weights', label: '评分权重', count: undefined })

  return (
    <QueryState
      isLoading={taskQuery.isLoading || planQuery.isLoading}
      isError={taskQuery.isError || planQuery.isError}
      error={taskQuery.error ?? planQuery.error}
      onRetry={() => {
        void taskQuery.refetch()
        void planQuery.refetch()
      }}
      isEmpty={!plan}
      emptyTitle="暂无计划"
      emptyDescription="计划尚未生成，请返回创建页或触发生成。"
    >
      {task && plan && (
        <div className="space-y-6 max-w-7xl mx-auto">
          {/* ── 状态引导 ───────────────────────────── */}
          <StatusGuide
            title={guide.title}
            whatNow={guide.whatNow}
            blockReason={blockReason}
            primaryAction={primaryAction}
            severity={blockReason ? 'warning' : needsApproval ? 'info' : undefined}
            statusBadge={<TaskStatusBadge status={task.status} />}
            hint={!blockReason && task?.status === 'PLANNING' ? '计划正在生成中，请稍候...' : undefined}
          />

          {/* ── 主布局 ────────────────────────────── */}
          <PageLayout ratio="3:1">
            <PrimaryWorkArea title="调研计划详情">
              <SectionTabs
                tabs={sectionTabs}
                activeTab={activeSection}
                onTabChange={setActiveSection}
              />

              {/* ── 计划步骤 tab ──────────────────── */}
              {activeSection === 'steps' && (
                <div className="space-y-3 pt-2">
                  {plan.clarifying_questions.length > 0 && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-base">澄清问题</CardTitle>
                        <CardDescription>
                          必填项未完成时无法提交澄清或批准计划。
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {plan.clarifying_questions.map((q) => (
                          <div key={q.id} className="space-y-2 rounded-lg border p-3">
                            <Label>
                              {q.question}
                              {q.required && (
                                <span className="ml-1 text-destructive">*</span>
                              )}
                            </Label>
                            {q.options.length > 0 ? (
                              <select
                                className="flex h-9 w-full rounded-md border border-input px-3 text-sm"
                                value={clarificationAnswers[q.id] ?? ''}
                                onChange={(e) =>
                                  setClarificationAnswer(q.id, e.target.value)
                                }
                                disabled={!needsClarification}
                              >
                                <option value="">请选择</option>
                                {q.options.map((opt) => (
                                  <option key={opt} value={opt}>
                                    {opt}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <Input
                                value={clarificationAnswers[q.id] ?? ''}
                                onChange={(e) =>
                                  setClarificationAnswer(q.id, e.target.value)
                                }
                                disabled={!needsClarification}
                              />
                            )}
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">计划步骤</CardTitle>
                      <CardDescription>
                        可启用/禁用步骤；高风险步骤执行时将再次拦截审批。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {plan.proposed_steps.map((step) => {
                        const enabled = !disabledStepIds.has(step.id)
                        const isHighRisk =
                          step.risk_level === 'high' || step.requires_approval
                        const toolCopy = STEP_TOOL_COPY[step.tool]
                        const riskCopy = RISK_LEVEL_COPY[step.risk_level]
                        return (
                          <div
                            key={step.id}
                            className={cn(
                              'rounded-lg border p-4',
                              !enabled && 'opacity-50',
                              isHighRisk && 'border-amber-400 bg-amber-50/50',
                            )}
                          >
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{step.title}</span>
                                  {isHighRisk && (
                                    <AlertTriangle
                                      className="h-4 w-4 text-amber-600"
                                      aria-label="需审批"
                                    />
                                  )}
                                </div>
                                <p className="mt-1 text-sm text-muted-foreground">
                                  {step.description}
                                </p>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {toolCopy && (
                                  <Badge variant="outline" title={step.tool}>
                                    {toolCopy.label}
                                  </Badge>
                                )}
                                {riskCopy && (
                                  <Badge variant="outline" title={step.risk_level}>
                                    {riskCopy.label}
                                  </Badge>
                                )}
                                {step.requires_approval && (
                                  <Badge className="bg-amber-100 text-amber-900">
                                    需审批
                                  </Badge>
                                )}
                              </div>
                            </div>
                            {needsApproval && step.user_editable && (
                              <label className="mt-3 flex items-center gap-2 text-sm">
                                <input
                                  type="checkbox"
                                  checked={enabled}
                                  onChange={() => toggleStep(step.id)}
                                  className="h-4 w-4"
                                />
                                启用此步骤
                              </label>
                            )}
                          </div>
                        )
                      })}
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* ── 候选仓库 tab ──────────────────── */}
              {activeSection === 'repos' && (
                <Card className="mt-2">
                  <CardHeader>
                    <CardTitle className="text-base">候选仓库</CardTitle>
                    <CardDescription>
                      根据研究目标自动发现的高相关热门仓库。请勾选 1–5 个作为调研对象。
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {discoveryNote && (
                      <div className="rounded-md border border-blue-400 bg-blue-50 p-2 text-sm text-blue-800">
                        {discoveryNote}
                      </div>
                    )}
                    {candidates.map((c) => {
                      const checked = selectedRepoUrls.includes(c.repo_url)
                      return (
                        <label
                          key={c.repo_url}
                          className={cn(
                            'flex cursor-pointer gap-3 rounded-lg border p-3',
                            checked && 'border-emerald-400 bg-emerald-50/40',
                          )}
                        >
                          <input
                            type="checkbox"
                            className="mt-1 h-4 w-4"
                            checked={checked}
                            onChange={() => toggleRepo(c.repo_url)}
                            disabled={!isWaitingUser || selectCandidates.isPending}
                          />
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <a
                                href={c.repo_url}
                                target="_blank"
                                rel="noreferrer"
                                className="truncate font-medium text-blue-700 hover:underline"
                              >
                                {c.repo_name}
                              </a>
                              <Badge variant="outline">★ {c.stars}</Badge>
                              {c.language && (
                                <Badge variant="outline">{c.language}</Badge>
                              )}
                              <Badge
                                className={
                                  c.discovered_by === 'user_seed'
                                    ? 'bg-slate-100 text-slate-700'
                                    : 'bg-blue-100 text-blue-900'
                                }
                              >
                                {c.discovered_by === 'user_seed'
                                  ? '种子'
                                  : `相关度 ${(c.relevance_score * 100).toFixed(0)}%`}
                              </Badge>
                            </div>
                            {c.description && (
                              <p className="line-clamp-2 text-sm text-muted-foreground">
                                {c.description}
                              </p>
                            )}
                            {c.relevance_reason && (
                              <p className="text-xs text-muted-foreground">
                                理由：{c.relevance_reason}
                              </p>
                            )}
                          </div>
                        </label>
                      )
                    })}
                    {isWaitingUser && (
                      <div className="flex items-center gap-3 pt-2">
                        <Button
                          type="button"
                          onClick={handleConfirmSelection}
                          disabled={!selectionValid || selectCandidates.isPending}
                        >
                          确认调研仓库（{selectedRepoUrls.length}）
                        </Button>
                        {!selectionValid && (
                          <span className="text-sm text-destructive">
                            请选择 1–5 个仓库
                          </span>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* ── 评分权重 tab ──────────────────── */}
              {activeSection === 'weights' && (
                <Card className="mt-2">
                  <CardHeader>
                    <CardTitle className="text-base">报告评分权重</CardTitle>
                    <CardDescription>
                      权重之和须约等于 1.0（当前：
                      {rubricWeightsSum(rubricWeights).toFixed(2)}）
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid gap-3 sm:grid-cols-2">
                    {Object.entries(rubricWeights).map(([key, value]) => (
                      <div key={key} className="space-y-1">
                        <Label htmlFor={`rubric-${key}`}>{key}</Label>
                        <Input
                          id={`rubric-${key}`}
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          value={value}
                          onChange={(e) =>
                            setRubricWeight(key, parseFloat(e.target.value) || 0)
                          }
                          disabled={!needsApproval}
                        />
                      </div>
                    ))}
                    {!rubricValid && (
                      <p className="text-sm text-destructive sm:col-span-2">
                        权重之和必须约等于 1.0
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}
            </PrimaryWorkArea>

            {/* ── 辅助面板 ────────────────────────── */}
            <SupportingPanel title="辅助信息">
              <div className="space-y-4">
                {/* 已确认上下文 */}
                <div>
                  <h5 className="text-xs font-medium text-muted-foreground mb-1">
                    已确认上下文
                  </h5>
                  <ul className="list-inside list-disc space-y-1 text-xs">
                    {plan.confirmed_context.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>

                {/* 未知项 */}
                {plan.unknowns.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-muted-foreground mb-1">
                      未知项
                    </h5>
                    <ul className="list-inside list-disc space-y-1 text-xs">
                      {plan.unknowns.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 风险摘要 */}
                {plan.risk_summary.length > 0 && (
                  <div>
                    <h5 className="text-xs font-medium text-amber-700 mb-1">
                      风险摘要
                    </h5>
                    <ul className="list-inside list-disc space-y-1 text-xs">
                      {plan.risk_summary.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 证据摘要（如果有） */}
                {plan.proposed_steps.some(
                  (s) => (s as any).evidence_ids?.length > 0,
                ) && (
                  <EvidenceSummary
                    evidenceIds={
                      plan.proposed_steps.flatMap(
                        (s) => (s as any).evidence_ids ?? [],
                      ) as string[]
                    }
                  />
                )}
              </div>
            </SupportingPanel>
          </PageLayout>

          {/* ── 操作栏 ────────────────────────────── */}
          <NextActionBar
            primary={
              needsApproval
                ? {
                    label: CTA_COPY.approve,
                    onClick: () => setConfirmApprove(true),
                    disabled: !rubricValid || approvePlan.isPending || noRepoSelected,
                  }
                : needsClarification
                  ? {
                      label: '提交澄清',
                      onClick: handleSubmitClarifications,
                      disabled:
                        submitClarifications.isPending ||
                        missingClarifications.length > 0,
                    }
                  : isApproved
                    ? { label: '查看工作流', href: `/tasks/${taskId}/workflow` }
                    : undefined
            }
            secondary={[
              ...(canRegeneratePlan
                ? [{ label: '重新生成', onClick: handleRegenerate }]
                : []),
              ...(canReplan
                ? [{ label: '重规划', onClick: () => setConfirmReplan(true) }]
                : []),
            ]}
            backTo={{ label: CTA_COPY.backToHistory, href: '/history' }}
          />

          {/* ── 次级导航 ────────────────────────── */}
          <SecondaryNavigation
            items={[
              ...(isApproved || isExecuting || isPostReport
                ? [
                    {
                      label: CTA_COPY.viewWorkflow,
                      href: `/tasks/${taskId}/workflow`,
                    },
                  ]
                : []),
              ...(isPostReport
                ? [
                    {
                      label: CTA_COPY.viewReport,
                      href: `/tasks/${taskId}/report`,
                    },
                  ]
                : []),
            ]}
          />

          {/* ── 批准确认 Dialog ─────────────────── */}
          <Dialog open={confirmApprove} onOpenChange={setConfirmApprove}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>确认批准计划？</DialogTitle>
                <DialogDescription>
                  批准后将进入执行阶段。高风险步骤执行时可能需要再次审批。
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setConfirmApprove(false)}
                >
                  取消
                </Button>
                <Button
                  onClick={handleApprove}
                  disabled={approvePlan.isPending}
                >
                  确认批准
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* ── 重规划确认 Dialog ────────────────── */}
          <Dialog open={confirmReplan} onOpenChange={setConfirmReplan}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>确认重规划？</DialogTitle>
                <DialogDescription>
                  将基于当前上下文重新生成计划。仅在等待批准、计划已批准或执行中状态可用。
                </DialogDescription>
              </DialogHeader>
              <Input
                placeholder="重规划原因（可选）"
                value={replanReason}
                onChange={(e) => setReplanReason(e.target.value)}
              />
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setConfirmReplan(false)}
                >
                  取消
                </Button>
                <Button
                  onClick={handleReplan}
                  disabled={replan.isPending || !canReplan}
                >
                  确认重规划
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </QueryState>
  )
}

function rubricWeightsSum(weights: Record<string, number>): number {
  return Object.values(weights).reduce((a, b) => a + b, 0)
}
