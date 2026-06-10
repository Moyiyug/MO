import { useCallback, useEffect, useMemo } from 'react'
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

import { usePlan, useTask } from '@/api/tasks'
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { buildStepGraph } from '@/features/workflow/buildGraph'
import { StepNode } from '@/features/workflow/StepNode'
import { useWorkflowStore } from '@/stores/workflowStore'
import { WAITING_USER_TASK_STATUSES } from '@/types/enums'
import { cn } from '@/lib/utils'

const nodeTypes = { stepNode: StepNode }

/** P-003 Workflow — 静态计划节点图（M4 接 SSE） */
function WorkflowCanvas() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: plan, isLoading, isError, error, refetch } = usePlan(taskId)
  const { data: task } = useTask(taskId)
  const { drawerOpen, selectedStep, openDrawer, closeDrawer } =
    useWorkflowStore()

  const graph = useMemo(
    () => (plan ? buildStepGraph(plan.proposed_steps) : { nodes: [], edges: [] }),
    [plan],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges)

  useEffect(() => {
    setNodes(graph.nodes)
    setEdges(graph.edges)
  }, [graph, setNodes, setEdges])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: { id: string }) => {
      const step = plan?.proposed_steps.find((s) => s.id === node.id)
      if (step) openDrawer(step)
    },
    [plan, openDrawer],
  )

  const isWaitingUser =
    task && WAITING_USER_TASK_STATUSES.includes(task.status)

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
          {isWaitingUser && (
            <div
              className={cn(
                'rounded-lg border-2 border-amber-500 bg-amber-50 p-4 text-amber-900 ring-2 ring-amber-400',
              )}
              role="alert"
            >
              <p className="font-medium">工作流暂停 — 等待用户操作</p>
              <p className="mt-1 text-sm">
                请返回{' '}
                <Link
                  to={`/tasks/${taskId}/plan`}
                  className="underline font-medium"
                >
                  计划审阅
                </Link>{' '}
                完成澄清或批准。
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold">工作流</h1>
              <p className="text-sm text-muted-foreground">
                当前为计划态静态视图；执行状态将在 M4 通过 SSE 实时更新。
              </p>
            </div>
            <div className="flex items-center gap-2">
              <TaskStatusBadge status={task.status} />
              <Button variant="outline" size="sm" asChild>
                <Link to={`/tasks/${taskId}/report`}>查看报告</Link>
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">节点图</CardTitle>
              <CardDescription>点击节点查看详情</CardDescription>
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
                  <dl className="grid grid-cols-2 gap-2">
                    <dt className="text-muted-foreground">工具</dt>
                    <dd>{selectedStep.tool}</dd>
                    <dt className="text-muted-foreground">风险</dt>
                    <dd>{selectedStep.risk_level}</dd>
                    <dt className="text-muted-foreground">需审批</dt>
                    <dd>{selectedStep.requires_approval ? '是' : '否'}</dd>
                    <dt className="text-muted-foreground">状态</dt>
                    <dd>计划待定（pending）</dd>
                  </dl>
                  {selectedStep.expected_outputs.length > 0 && (
                    <div>
                      <p className="font-medium">预期产出</p>
                      <ul className="mt-1 list-inside list-disc">
                        {selectedStep.expected_outputs.map((o) => (
                          <li key={o}>{o}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {selectedStep.depends_on.length > 0 && (
                    <div>
                      <p className="font-medium">依赖</p>
                      <p className="text-muted-foreground">
                        {selectedStep.depends_on.join(', ')}
                      </p>
                    </div>
                  )}
                  <p className="rounded-md bg-muted p-2 text-xs text-muted-foreground">
                    下一步：等待 M4 事件流推送实际执行状态与 next_action。
                  </p>
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
