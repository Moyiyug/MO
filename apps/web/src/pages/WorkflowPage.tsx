import { useCallback, useEffect, useMemo, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { toast } from 'sonner'

import { subscribeEvents, useApproveStep, useStartExecution } from '@/api/events'
import { usePlan, useTask } from '@/api/tasks'
import {
  NodeStatusBadge,
  TaskStatusBadge,
} from '@/components/common/StatusBadge'
import { QueryState } from '@/components/common/QueryState'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { buildStepGraph } from '@/features/workflow/buildGraph'
import { StepNode } from '@/features/workflow/StepNode'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WAITING_USER_TASK_STATUSES } from '@/types/enums'
import { cn } from '@/lib/utils'

const nodeTypes = { stepNode: StepNode }

const EXECUTION_STATUSES = new Set([
  'EXECUTING',
  'REPORT_DRAFT',
  'REVIEW_REQUIRED',
  'DONE',
  'FAILED',
])

/** P-003 Workflow — SSE 实时节点图（F-010） */
function WorkflowCanvas() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: plan, isLoading, isError, error, refetch } = usePlan(taskId)
  const { data: task, refetch: refetchTask } = useTask(taskId)

  const startExecution = useStartExecution()
  const approveStep = useApproveStep()

  const {
    drawerOpen,
    selectedStep,
    nodeStatuses,
    eventsByNode,
    lastSeq,
    openDrawer,
    closeDrawer,
    reset,
    applyEvent,
    getNodeEvent,
  } = useWorkflowStore()

  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (taskId) reset(taskId)
  }, [taskId, reset])

  const graph = useMemo(
    () =>
      plan
        ? buildStepGraph(plan.proposed_steps, nodeStatuses)
        : { nodes: [], edges: [] },
    [plan, nodeStatuses],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges)

  useEffect(() => {
    setNodes(graph.nodes)
    setEdges(graph.edges)
  }, [graph, setNodes, setEdges])

  const shouldSubscribe =
    task && EXECUTION_STATUSES.has(task.status) && Boolean(taskId)

  useEffect(() => {
    if (!shouldSubscribe || !taskId) return

    let unsubscribe: (() => void) | null = null
    let disposed = false
    let since = useWorkflowStore.getState().lastSeq
    const clearReconnectTimer = () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    const connect = () => {
      if (disposed) return
      clearReconnectTimer()
      unsubscribe?.()
      unsubscribe = subscribeEvents(
        taskId,
        (event) => {
          if (disposed) return
          applyEvent(event)
          since = event.seq
          const latestStatuses = useWorkflowStore.getState().nodeStatuses
          const allStepsSettled =
            plan?.proposed_steps.every(
              (s) =>
                s.status === 'skipped' ||
                latestStatuses[s.id] === 'completed' ||
                latestStatuses[s.id] === 'skipped',
            ) ?? false
          if (
            (event.status === 'completed' || event.status === 'skipped') &&
            allStepsSettled
          ) {
            void refetchTask()
          }
          if (event.status === 'failed') {
            void refetchTask()
          }
        },
        {
          since,
          onError: () => {
            if (disposed) return
            clearReconnectTimer()
            reconnectTimer.current = setTimeout(connect, 2000)
          },
        },
      )
    }

    connect()

    return () => {
      disposed = true
      unsubscribe?.()
      clearReconnectTimer()
    }
  }, [shouldSubscribe, taskId, applyEvent, refetchTask, plan])

  useEffect(() => {
    if (task?.status === 'REPORT_DRAFT') {
      void refetchTask()
    }
  }, [lastSeq, task?.status, refetchTask])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      const step = plan?.proposed_steps.find((s) => s.id === node.id)
      if (step) openDrawer(step)
    },
    [plan, openDrawer],
  )

  const selectedEvent = selectedStep ? getNodeEvent(selectedStep.id) : undefined
  const waitingStep = plan?.proposed_steps.find(
    (s) => nodeStatuses[s.id] === 'waiting_user',
  )
  const isPlanWaitingUser =
    task && WAITING_USER_TASK_STATUSES.includes(task.status)

  const handleStart = async () => {
    if (!taskId) return
    try {
      await startExecution.mutateAsync(taskId)
      toast.success('执行已启动')
      void refetchTask()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '启动失败')
    }
  }

  const handleStepApprove = async (approved: boolean) => {
    if (!taskId || !selectedStep) return
    try {
      await approveStep.mutateAsync({
        taskId,
        stepId: selectedStep.id,
        approved,
      })
      toast.success(approved ? '步骤已批准' : '步骤已拒绝')
      if (!approved) void refetchTask()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError}
      error={error}
      onRetry={() => void refetch()}
      isEmpty={!plan || plan.proposed_steps.length === 0}
      emptyTitle="暂无工作流步骤"
      emptyDescription="请先完成计划审阅并批准计划。"
    >
      {plan && task && (
        <div className="space-y-4">
          {isPlanWaitingUser && (
            <div
              className={cn(
                'rounded-lg border-2 border-amber-500 bg-amber-50 p-4 text-amber-900 ring-2 ring-amber-400',
              )}
              role="alert"
            >
              <p className="font-medium">计划阶段暂停 — 等待用户操作</p>
              <p className="mt-1 text-sm">
                请返回{' '}
                <Link
                  to={`/tasks/${taskId}/plan`}
                  className="font-medium underline"
                >
                  计划审阅
                </Link>{' '}
                完成澄清或批准。
              </p>
            </div>
          )}

          {waitingStep && (
            <div
              className={cn(
                'rounded-lg border-2 border-amber-500 bg-amber-50 p-4 text-amber-900 ring-2 ring-amber-400',
              )}
              role="alert"
            >
              <p className="font-medium">执行暂停 — 等待步骤审批</p>
              <p className="mt-1 text-sm">
                节点「{waitingStep.title}」需要您的审批才能继续。
                {eventsByNode[waitingStep.id]?.next_action && (
                  <span className="mt-1 block">
                    {eventsByNode[waitingStep.id].next_action}
                  </span>
                )}
              </p>
              <Button
                size="sm"
                className="mt-3"
                onClick={() => openDrawer(waitingStep)}
              >
                查看并审批
              </Button>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">工作流</h1>
              <p className="text-sm text-muted-foreground">
                节点状态由后端 SSE 事件实时推送（F-010）。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <TaskStatusBadge status={task.status} />
              {task.status === 'PLAN_APPROVED' && (
                <Button
                  size="sm"
                  onClick={handleStart}
                  disabled={startExecution.isPending}
                >
                  开始执行
                </Button>
              )}
              <Button variant="outline" size="sm" asChild>
                <Link to={`/tasks/${taskId}/report`}>查看报告</Link>
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">节点图</CardTitle>
              <CardDescription>点击节点查看详情与审批</CardDescription>
            </CardHeader>
            <CardContent className="h-[480px] p-0">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background />
                <Controls />
              </ReactFlow>
            </CardContent>
          </Card>

          <Dialog open={drawerOpen} onOpenChange={(o) => !o && closeDrawer()}>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>{selectedStep?.title}</DialogTitle>
              </DialogHeader>
              {selectedStep && (
                <div className="space-y-3 text-sm">
                  <p>{selectedStep.description}</p>
                  {nodeStatuses[selectedStep.id] && (
                    <NodeStatusBadge status={nodeStatuses[selectedStep.id]} />
                  )}
                  <dl className="grid grid-cols-2 gap-2">
                    <dt className="text-muted-foreground">工具</dt>
                    <dd>{selectedStep.tool}</dd>
                    <dt className="text-muted-foreground">风险</dt>
                    <dd>{selectedStep.risk_level}</dd>
                    <dt className="text-muted-foreground">需审批</dt>
                    <dd>{selectedStep.requires_approval ? '是' : '否'}</dd>
                  </dl>
                  {selectedEvent?.input_summary && (
                    <div>
                      <p className="font-medium">输入摘要</p>
                      <p className="text-muted-foreground">
                        {selectedEvent.input_summary}
                      </p>
                    </div>
                  )}
                  {selectedEvent?.output_summary && (
                    <div>
                      <p className="font-medium">输出摘要</p>
                      <p className="text-muted-foreground">
                        {selectedEvent.output_summary}
                      </p>
                    </div>
                  )}
                  {selectedEvent && (
                    <div>
                      <p className="font-medium">证据 ID</p>
                      {selectedEvent.evidence_ids &&
                      selectedEvent.evidence_ids.length > 0 ? (
                        <div className="mt-1 flex flex-wrap gap-2">
                          {selectedEvent.evidence_ids.map((id) => (
                            <code
                              key={id}
                              className="rounded bg-muted px-1.5 py-0.5 text-xs"
                            >
                              {id}
                            </code>
                          ))}
                        </div>
                      ) : (
                        <p className="text-muted-foreground">暂无证据 ID</p>
                      )}
                    </div>
                  )}
                  {selectedEvent?.logs && selectedEvent.logs.length > 0 && (
                    <div>
                      <p className="font-medium">日志</p>
                      <ul className="mt-1 list-inside list-disc text-muted-foreground">
                        {selectedEvent.logs.map((log) => (
                          <li key={log}>{log}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedEvent?.error_message && (
                    <p className="text-destructive">{selectedEvent.error_message}</p>
                  )}
                  {selectedEvent?.next_action && (
                    <p className="rounded-md bg-amber-50 p-2 text-amber-900">
                      {selectedEvent.next_action}
                    </p>
                  )}
                  {nodeStatuses[selectedStep.id] === 'waiting_user' && (
                    <DialogFooter className="gap-2 sm:justify-start">
                      <Button
                        size="sm"
                        onClick={() => handleStepApprove(true)}
                        disabled={approveStep.isPending}
                      >
                        批准步骤
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleStepApprove(false)}
                        disabled={approveStep.isPending}
                      >
                        拒绝
                      </Button>
                    </DialogFooter>
                  )}
                </div>
              )}
            </DialogContent>
          </Dialog>
        </div>
      )}
    </QueryState>
  )
}

export function WorkflowPage() {
  return (
    <ReactFlowProvider>
      <WorkflowCanvas />
    </ReactFlowProvider>
  )
}
