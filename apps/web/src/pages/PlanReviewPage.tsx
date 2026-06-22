import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ArrowRight, CheckCircle2, CircleAlert } from 'lucide-react'
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
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { MetricChip } from '@/components/common/visual'
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
  COMPARISON_DIMENSION_COPY,
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
  const [selectedRepoUrlsByPlanId, setSelectedRepoUrlsByPlanId] = useState<
    Record<string, string[]>
  >({})
  const [activeSectionByPlanId, setActiveSectionByPlanId] = useState<
    Record<string, string>
  >({})

  const task = taskQuery.data
  const plan = planQuery.data

  useEffect(() => {
    if (!plan) return
    initFromPlan(plan)
  }, [plan, initFromPlan])

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
  const serverSelectedRepoUrls = useMemo(
    () => plan?.repo_candidates.filter((c) => c.selected).map((c) => c.repo_url) ?? [],
    [plan],
  )
  const selectedRepoUrls =
    plan ? selectedRepoUrlsByPlanId[plan.id] ?? serverSelectedRepoUrls : []
  const discoveryNote = repoCandidatesQuery.data?.discovery_note ?? null
  const hasCandidates = candidates.length > 0
  const noRepoSelected = (task?.repo_urls?.length ?? 0) === 0
  const selectionValid =
    selectedRepoUrls.length >= 1 && selectedRepoUrls.length <= 5
  const highRiskSteps =
    plan?.proposed_steps.filter(
      (step) => step.risk_level === 'high' || step.requires_approval,
    ) ?? []
  const hasClarifications = (plan?.clarifying_questions.length ?? 0) > 0
  const rubricTotal = rubricWeightsSum(rubricWeights)
  const preferredSection =
    missingClarifications.length > 0
      ? 'clarify'
      : noRepoSelected && hasCandidates
        ? 'repos'
        : 'steps'
  const activeSection = plan
    ? activeSectionByPlanId[plan.id] ?? preferredSection
    : preferredSection
  const setActiveSection = (section: string) => {
    if (!plan) return
    setActiveSectionByPlanId((prev) => ({ ...prev, [plan.id]: section }))
  }

  // ── StatusGuide 推导 ───────────────────────────────────────
  const guide = PAGE_GUIDE_COPY.planReview
  let blockReason: string | undefined
  if (isWaitingUser && noRepoSelected) {
    blockReason = guide.blockReasons.noRepoSelected
  } else if (isWaitingUser && missingClarifications.length > 0) {
    blockReason = guide.blockReasons.unansweredRequired
  } else if (needsApproval && !rubricValid) {
    blockReason = '评分权重之和必须约等于 1.0'
  }

  const primaryAction = !blockReason && needsApproval
    ? {
        label: CTA_COPY.approve,
        onClick: () => setConfirmApprove(true),
        disabled: approvePlan.isPending,
      }
    : !blockReason && needsClarification
      ? {
          label: '提交澄清',
          onClick: handleSubmitClarifications,
          disabled: submitClarifications.isPending,
        }
      : !blockReason && isApproved
        ? { label: '查看工作流', href: `/tasks/${taskId}/workflow` }
        : undefined

  // ── helpers ────────────────────────────────────────────────
  const toggleRepo = (url: string) => {
    if (!plan) return
    setSelectedRepoUrlsByPlanId((prev) => {
      const current = prev[plan.id] ?? serverSelectedRepoUrls
      const next = current.includes(url)
        ? current.filter((u) => u !== url)
        : [...current, url]
      return { ...prev, [plan.id]: next }
    })
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
  if (hasClarifications) {
    sectionTabs.unshift({
      id: 'clarify',
      label: '澄清问题',
      count: plan?.clarifying_questions.length,
    })
  }
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
        <div className="mo-page-shell">
          {/* ── 状态引导 ───────────────────────────── */}
          <StatusGuide
            title={guide.title}
            whatNow={guide.whatNow}
            blockReason={blockReason}
            primaryAction={primaryAction}
            severity={blockReason ? 'warning' : needsApproval ? 'info' : undefined}
            statusBadge={<TaskStatusBadge status={task.status} />}
            hint={!blockReason && task?.status === 'PLANNING' ? '计划正在生成中，请稍候...' : undefined}
            ornament="research-flow"
            ornamentLabel={false}
          />

          <PageCommandBar
            position="top"
            title="计划工具"
            description="这些操作不会绕过审批；真正推进任务请使用上方主按钮。"
            secondary={[
              ...(canRegeneratePlan
                ? [{ label: '重新生成', onClick: handleRegenerate }]
                : []),
              ...(canReplan
                ? [{ label: '重规划', onClick: () => setConfirmReplan(true) }]
                : []),
            ]}
          />

          {/* ── 主布局 ────────────────────────────── */}
          <PageLayout ratio="3:1">
            <PrimaryWorkArea title="调研计划详情">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">批准检查清单</CardTitle>
                  <CardDescription>
                    这些条件决定计划是否可以进入执行；高风险步骤在执行时仍会再次审批。
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <ChecklistItem
                    ok={!noRepoSelected}
                    label="已确认仓库"
                    detail={
                      noRepoSelected
                        ? selectedRepoUrls.length > 0
                          ? '已勾选候选仓库，请先点击确认调研仓库写回。'
                          : '请至少确认 1 个仓库；仓库可以来自自动候选。'
                        : `${task.repo_urls.length} 个仓库已写回任务。`
                    }
                  />
                  <ChecklistItem
                    ok={missingClarifications.length === 0}
                    label="必答澄清"
                    detail={
                      missingClarifications.length === 0
                        ? '必答项已完成。'
                        : `还有 ${missingClarifications.length} 个必答问题未完成。`
                    }
                  />
                  <ChecklistItem
                    ok={rubricValid}
                    label="评分权重"
                    detail={`当前总和 ${rubricTotal.toFixed(2)}，必须等于 1.00。`}
                  />
                  <ChecklistItem
                    ok={highRiskSteps.length === 0}
                    warning={highRiskSteps.length > 0}
                    label="高风险步骤"
                    detail={
                      highRiskSteps.length > 0
                        ? `${highRiskSteps.length} 个步骤含高风险或需审批，执行时会再次拦截。`
                        : '未发现高风险步骤。'
                    }
                  />
                </CardContent>
              </Card>

              <SectionTabs
                tabs={sectionTabs}
                activeTab={activeSection}
                onTabChange={setActiveSection}
              />

              {activeSection === 'clarify' && (
                <Card className="mt-2">
                  <CardHeader>
                    <CardTitle className="text-base">澄清问题</CardTitle>
                    <CardDescription>
                      先回答必填项，系统会把答案写回计划上下文后再允许批准。
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
                    {needsClarification && (
                      <Button
                        type="button"
                        onClick={handleSubmitClarifications}
                        disabled={missingClarifications.length > 0 || submitClarifications.isPending}
                      >
                        提交澄清
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* ── 计划步骤 tab ──────────────────── */}
              {activeSection === 'steps' && (
                <div className="space-y-3 pt-2">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">计划步骤</CardTitle>
                      <CardDescription>
                        可启用/禁用步骤；高风险步骤执行时将再次拦截审批。
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="max-h-[32rem] space-y-3 overflow-y-auto pr-3">
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
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium break-words">{step.title}</span>
                                  {isHighRisk && (
                                    <AlertTriangle
                                      className="h-4 w-4 text-amber-600"
                                      aria-label="需审批"
                                    />
                                  )}
                                </div>
                                <p className="mt-1 break-words text-sm text-muted-foreground">
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
                  <CardContent className="max-h-[32rem] space-y-3 overflow-y-auto pr-3">
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
                            'flex cursor-pointer gap-3 rounded-lg border bg-background/72 p-3 shadow-[var(--mo-shadow-line)] transition-colors hover:border-blue-300',
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
                                className="max-w-full truncate font-medium text-blue-700 hover:underline"
                              >
                                {c.repo_name}
                              </a>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              <MetricChip label="stars" value={c.stars} tone="slate" />
                              {c.language && <MetricChip label={c.language} tone="violet" />}
                              <MetricChip
                                label={
                                  c.discovered_by === 'user_seed'
                                    ? '用户种子'
                                    : '自动发现'
                                }
                                value={
                                  c.discovered_by === 'user_seed'
                                    ? undefined
                                    : `${(c.relevance_score * 100).toFixed(0)}%`
                                }
                                tone={c.discovered_by === 'user_seed' ? 'slate' : 'blue'}
                              />
                            </div>
                            {c.description && (
                              <p className="line-clamp-2 text-sm text-muted-foreground">
                                {c.description}
                              </p>
                            )}
                            {c.relevance_reason && (
                              <p className="line-clamp-2 break-words text-xs text-muted-foreground">
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
                      权重之和须约等于 1.0（当前：{rubricTotal.toFixed(2)}）
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            rubricValid ? 'bg-emerald-500' : 'bg-amber-500',
                          )}
                          style={{ width: `${Math.max(4, Math.min(100, rubricTotal * 100))}%` }}
                        />
                      </div>
                      {!rubricValid && (
                        <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
                          权重总和需要等于 1.00 后才能批准计划。
                        </p>
                      )}
                    </div>
                    <div className="grid max-h-[24rem] gap-3 overflow-y-auto pr-3 sm:grid-cols-2">
                    {Object.entries(rubricWeights).map(([key, value]) => (
                      <div key={key} className="space-y-1">
                        <Label htmlFor={`rubric-${key}`}>
                          {COMPARISON_DIMENSION_COPY[key]?.label ?? key}
                        </Label>
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
                    </div>
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
                  (s) => getStepEvidenceIds(s).length > 0,
                ) && (
                  <EvidenceSummary
                    evidenceIds={
                      plan.proposed_steps.flatMap(getStepEvidenceIds)
                    }
                  />
                )}
              </div>
            </SupportingPanel>
          </PageLayout>

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

function ChecklistItem({
  ok,
  warning = false,
  label,
  detail,
}: {
  ok: boolean
  warning?: boolean
  label: string
  detail: string
}) {
  const tone = warning ? 'amber' : ok ? 'green' : 'red'
  const icon = ok && !warning
    ? <CheckCircle2 className="h-4 w-4" aria-hidden />
    : <CircleAlert className="h-4 w-4" aria-hidden />

  return (
    <div
      className={cn(
        'rounded-lg border p-3',
        tone === 'green' && 'border-emerald-300 bg-emerald-50/60',
        tone === 'amber' && 'border-amber-300 bg-amber-50/70',
        tone === 'red' && 'border-red-300 bg-red-50/60',
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-medium">{label}</span>
        <MetricChip
          label={warning ? '需关注' : ok ? '通过' : '未完成'}
          tone={tone}
          icon={icon}
        />
      </div>
      <p className="text-sm text-muted-foreground">{detail}</p>
    </div>
  )
}

function rubricWeightsSum(weights: Record<string, number>): number {
  return Object.values(weights).reduce((a, b) => a + b, 0)
}

function getStepEvidenceIds(step: unknown): string[] {
  if (typeof step !== 'object' || step === null || !('evidence_ids' in step)) {
    return []
  }
  const ids = (step as { evidence_ids?: unknown }).evidence_ids
  return Array.isArray(ids)
    ? ids.filter((id): id is string => typeof id === 'string')
    : []
}
