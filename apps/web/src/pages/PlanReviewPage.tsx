import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

import {
  useApprovePlan,
  useGeneratePlan,
  usePlan,
  useReplan,
  useSubmitClarifications,
  useTask,
} from '@/api/tasks'
import { QueryState } from '@/components/common/QueryState'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
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

/** P-002 PlanReview — PlanMode 核心 */
export function PlanReviewPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()

  const taskQuery = useTask(taskId)
  const planQuery = usePlan(taskId)
  const generatePlan = useGeneratePlan()
  const approvePlan = useApprovePlan()
  const replan = useReplan()
  const submitClarifications = useSubmitClarifications()

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

  const task = taskQuery.data
  const plan = planQuery.data

  useEffect(() => {
    if (plan) initFromPlan(plan)
  }, [plan, initFromPlan])

  const isWaitingUser =
    task && WAITING_USER_TASK_STATUSES.includes(task.status)
  const needsClarification = task?.status === 'WAITING_USER_CLARIFICATION'
  const needsApproval = task?.status === 'WAITING_USER_APPROVAL'
  const isApproved =
    task?.status === 'PLAN_APPROVED' || task?.status === 'EXECUTING'

  const missingClarifications = plan
    ? unansweredRequired(plan.clarifying_questions, clarificationAnswers)
    : []

  const rubricValid = isRubricValid(rubricWeights)

  const handleSubmitClarifications = async () => {
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

  const handleApprove = async () => {
    if (!taskId) return
    if (!rubricValid) {
      toast.error('评分权重之和必须约等于 1.0')
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

  const handleReplan = async () => {
    if (!taskId) return
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

  const handleRegenerate = async () => {
    if (!taskId) return
    try {
      await generatePlan.mutateAsync(taskId)
      toast.success('计划已重新生成')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '生成失败')
    }
  }

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
        <div className="space-y-6">
          {isWaitingUser && (
            <div
              className={cn(
                'rounded-lg border-2 border-amber-500 bg-amber-50 p-4 text-amber-900',
                'ring-2 ring-amber-400',
              )}
              role="alert"
            >
              <p className="font-medium">
                等待用户操作 — 流程已暂停
              </p>
              <p className="mt-1 text-sm">
                {needsClarification &&
                  '请回答下方澄清问题后继续。'}
                {needsApproval &&
                  '请审阅计划并批准后方可进入执行阶段（R-001）。'}
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">计划审阅</h1>
              <p className="text-sm text-muted-foreground">{plan.task_summary}</p>
            </div>
            <TaskStatusBadge status={task.status} />
          </div>

          <div className="flex flex-wrap gap-2">
            {needsClarification && (
              <Button
                onClick={handleSubmitClarifications}
                disabled={
                  submitClarifications.isPending ||
                  missingClarifications.length > 0
                }
              >
                提交澄清
              </Button>
            )}
            {needsApproval && (
              <Button
                onClick={() => setConfirmApprove(true)}
                disabled={!rubricValid || approvePlan.isPending}
              >
                批准计划
              </Button>
            )}
            <Button
              variant="outline"
              onClick={handleRegenerate}
              disabled={generatePlan.isPending || isApproved}
            >
              重新生成
            </Button>
            <Button
              variant="outline"
              onClick={() => setConfirmReplan(true)}
              disabled={replan.isPending}
            >
              重规划
            </Button>
            {isApproved && (
              <Button asChild>
                <Link to={`/tasks/${taskId}/workflow`}>查看工作流</Link>
              </Button>
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">已确认上下文</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1 text-sm">
                  {plan.confirmed_context.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">未知项</CardTitle>
              </CardHeader>
              <CardContent>
                {plan.unknowns.length === 0 ? (
                  <p className="text-sm text-muted-foreground">无</p>
                ) : (
                  <ul className="list-inside list-disc space-y-1 text-sm">
                    {plan.unknowns.map((u, i) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

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
                        <Badge variant="outline">{step.tool}</Badge>
                        <Badge variant="outline">{step.risk_level}</Badge>
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

          <Card>
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

          {plan.risk_summary.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">风险摘要</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1 text-sm">
                  {plan.risk_summary.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Dialog open={confirmApprove} onOpenChange={setConfirmApprove}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>确认批准计划？</DialogTitle>
                <DialogDescription>
                  批准后将进入执行阶段。高风险步骤执行时可能再次请求审批（R-001）。
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
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={confirmReplan} onOpenChange={setConfirmReplan}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>确认重规划？</DialogTitle>
                <DialogDescription>
                  将基于当前上下文重新生成计划（F-003）。
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
                <Button onClick={handleReplan} disabled={replan.isPending}>
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
