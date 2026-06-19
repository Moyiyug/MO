import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useParams } from 'react-router-dom'
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
import { StatusGuide } from '@/components/common/StatusGuide'
import {
  PageLayout,
  PrimaryWorkArea,
  SupportingPanel,
  SecondaryNavigation,
} from '@/components/common/InfoHierarchy'
import { SupportingDrawer } from '@/components/common/SupportingDrawer'
import { EvidenceSummary } from '@/components/common/EvidenceSummary'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { buildStepGraph } from '@/features/workflow/buildGraph'
import { StepNode } from '@/features/workflow/StepNode'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WAITING_USER_TASK_STATUSES } from '@/types/enums'
import {
  PAGE_GUIDE_COPY,
  CTA_COPY,
  NODE_TYPE_COPY,
  RISK_LEVEL_COPY,
} from '@/lib/uiCopy'

const nodeTypes = { stepNode: StepNode }

const EXECUTION_STATUSES = new Set([
  'EXECUTING',
  'REPORT_DRAFT',
  'REVIEW_REQUIRED',
  'DONE',
  'FAILED',
])

/** P-003 Workflow — SSE 实时节点图 */
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
                latestStatuses[s.node_id] === 'completed' ||
                latestStatuses[s.node_id] === 'skipped',
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
      const step = plan?.proposed_steps.find((s) => s.node_id === node.id)
      if (step) openDrawer(step)
    },
    [plan, openDrawer],
  )

  const selectedEvent = selectedStep ? getNodeEvent(selectedStep.node_id) : undefined
  const waitingStep = plan?.proposed_steps.find(
    (s) => nodeStatuses[s.node_id] === 'waiting_user',
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
        stepId: selectedStep.node_id,
        approved,
      })
      toast.success(approved ? '步骤已批准' : '步骤已拒绝')
      if (!approved) void refetchTask()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  // ── StatusGuide 推导 ───────────────────────────────────────
  const guide = PAGE_GUIDE_COPY.workflow
  let blockReason: string | undefined
  if (isPlanWaitingUser) {
    blockReason = '计划阶段尚未完成，请返回计划审阅页完成澄清或批准。'
  } else if (waitingStep) {
    blockReason = `节点「${waitingStep.title}」需要你的审批才能继续。`
  }

  const nodeTypeCopy = selectedStep ? NODE_TYPE_COPY[selectedStep.tool] : undefined
  const riskCopy = selectedStep ? RISK_LEVEL_COPY[selectedStep.risk_level] : undefined

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError}
      error={error}
      onRetry={() => void refetch()}
      isEmpty={!plan || plan.proposed_steps.length === 0}
      emptyTitle="暂无工作流步骤"
      emptyDescription="请先完成计划审阅并批准计划。"
      emptyAction={{ label: '返回计划审阅', href: `/tasks/${taskId}/plan` }}
    >
      {plan && task && (
        <div className="space-y-6 max-w-7xl mx-auto">
          <StatusGuide
            title={guide.title}
            whatNow={guide.whatNow}
            blockReason={blockReason}
            primaryAction={
              isPlanWaitingUser
                ? { label: '返回计划审阅', href: `/tasks/${taskId}/plan` }
                : waitingStep
                  ? {
                      label: guide.primaryAction,
                      onClick: () => waitingStep && openDrawer(waitingStep),
                    }
                  : task.status === 'PLAN_APPROVED'
                    ? { label: '开始执行', onClick: handleStart }
                    : undefined
            }
            statusBadge={<TaskStatusBadge status={task.status} />}
          />

          <PageLayout ratio="3:1">
            <PrimaryWorkArea title="执行工作流">
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
            </PrimaryWorkArea>

            {/* 辅助面板：执行进度摘要 */}
            <SupportingPanel title="执行状态">
              <div className="space-y-2">
                {plan.proposed_steps.map((s) => {
                  const status = nodeStatuses[s.node_id] ?? 'pending'
                  return (
                    <div key={s.node_id} className="flex items-center justify-between gap-2 text-xs">
                      <span className="truncate">{s.title}</span>
                      <NodeStatusBadge
                        status={status}
                        className="flex-shrink-0"
                      />
                    </div>
                  )
                })}
              </div>
              {selectedEvent?.evidence_ids && selectedEvent.evidence_ids.length > 0 && (
                <div className="mt-4">
                  <EvidenceSummary evidenceIds={selectedEvent.evidence_ids} />
                </div>
              )}
            </SupportingPanel>
          </PageLayout>

          <PageCommandBar
            position="top"
            title="工作流操作"
            description="等待确认时需要先处理审批节点，完成后可查看报告。"
            primary={
              task.status === 'PLAN_APPROVED'
                ? { label: '开始执行', onClick: handleStart }
                : waitingStep
                  ? {
                      label: guide.primaryAction,
                      onClick: () => waitingStep && openDrawer(waitingStep),
                    }
                  : task.status === 'REPORT_DRAFT' || task.status === 'DONE'
                    ? { label: CTA_COPY.viewReport, href: `/tasks/${taskId}/report` }
                    : undefined
            }
            secondary={[
              { label: '返回计划', href: `/tasks/${taskId}/plan` },
            ]}
          />

          <SecondaryNavigation
            items={[
              ...(task.status === 'REPORT_DRAFT' || task.status === 'REVIEW_REQUIRED' || task.status === 'DONE'
                ? [{ label: CTA_COPY.viewReport, href: `/tasks/${taskId}/report` }]
                : []),
            ]}
            backTo={{ label: CTA_COPY.backToHistory, href: '/history' }}
          />

          {/* 节点详情 Drawer */}
          <SupportingDrawer
            open={drawerOpen}
            onClose={closeDrawer}
            title={selectedStep?.title ?? '节点详情'}
            technical
          >
            {selectedStep && (
              <div className="space-y-4">
                <p>{selectedStep.description}</p>
                {nodeStatuses[selectedStep.node_id] && (
                  <NodeStatusBadge status={nodeStatuses[selectedStep.node_id]} />
                )}
                <dl className="grid grid-cols-2 gap-2">
                  <dt className="text-muted-foreground">工具</dt>
                  <dd title={selectedStep.tool}>
                    {nodeTypeCopy?.label ?? selectedStep.tool}
                  </dd>
                  <dt className="text-muted-foreground">风险</dt>
                  <dd title={selectedStep.risk_level}>
                    {riskCopy?.label ?? selectedStep.risk_level}
                  </dd>
                  <dt className="text-muted-foreground">需审批</dt>
                  <dd>{selectedStep.requires_approval ? '是' : '否'}</dd>
                </dl>
                {selectedEvent?.input_summary && (
                  <div>
                    <p className="font-medium">输入摘要</p>
                    <p className="text-muted-foreground">{selectedEvent.input_summary}</p>
                  </div>
                )}
                {selectedEvent?.output_summary && (
                  <div>
                    <p className="font-medium">输出摘要</p>
                    <p className="text-muted-foreground">{selectedEvent.output_summary}</p>
                  </div>
                )}
                {selectedEvent && (
                  <EvidenceSummary
                    evidenceIds={selectedEvent.evidence_ids ?? []}
                  />
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
                {nodeStatuses[selectedStep.node_id] === 'waiting_user' && (
                  <div className="flex gap-2 pt-2 border-t">
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
                  </div>
                )}
              </div>
            )}
          </SupportingDrawer>
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
