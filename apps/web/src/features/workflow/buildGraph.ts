import type { Edge, Node } from '@xyflow/react'

import type { PlanStep } from '@/types/plan'
import type { NodeStatus } from '@/types/enums'

export type StepNodeData = {
  step: PlanStep
  /** M3 静态计划态 — 不伪造 running/completed */
  displayStatus: NodeStatus
  label: string
} & Record<string, unknown>

const H_GAP = 280
const V_GAP = 120

export function stepStatusToDisplayStatus(step: PlanStep): NodeStatus {
  if (step.status === 'skipped') return 'skipped'
  return 'pending'
}

/** 按 depends_on 拓扑分层布局；statusMap 来自 SSE 事件 */
export function buildStepGraph(
  steps: PlanStep[],
  statusMap: Record<string, NodeStatus> = {},
): {
  nodes: Node<StepNodeData>[]
  edges: Edge[]
} {
  if (steps.length === 0) {
    return { nodes: [], edges: [] }
  }

  const depth = new Map<string, number>()
  const byId = new Map(steps.map((s) => [s.id, s]))

  function getDepth(id: string, visiting = new Set<string>()): number {
    if (depth.has(id)) return depth.get(id)!
    if (visiting.has(id)) return 0
    visiting.add(id)
    const step = byId.get(id)
    if (!step || step.depends_on.length === 0) {
      depth.set(id, 0)
      return 0
    }
    const d =
      1 + Math.max(...step.depends_on.map((dep) => getDepth(dep, visiting)))
    depth.set(id, d)
    return d
  }

  for (const s of steps) getDepth(s.id)

  const layers = new Map<number, PlanStep[]>()
  for (const s of steps) {
    const d = depth.get(s.id) ?? 0
    if (!layers.has(d)) layers.set(d, [])
    layers.get(d)!.push(s)
  }

  const nodes: Node<StepNodeData>[] = []
  for (const [d, layerSteps] of layers) {
    layerSteps.forEach((step, i) => {
      nodes.push({
        id: step.id,
        type: 'stepNode',
        position: { x: d * H_GAP, y: i * V_GAP },
        data: {
          step,
          displayStatus:
            statusMap[step.id] ?? stepStatusToDisplayStatus(step),
          label: step.title,
        },
      })
    })
  }

  const edges: Edge[] = []
  for (const step of steps) {
    for (const dep of step.depends_on) {
      if (byId.has(dep)) {
        const targetStatus = statusMap[step.id]
        edges.push({
          id: `${dep}->${step.id}`,
          source: dep,
          target: step.id,
          animated: targetStatus === 'running',
        })
      }
    }
  }

  return { nodes, edges }
}
