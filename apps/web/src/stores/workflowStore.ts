import { create } from 'zustand'

import type { NodeEvent } from '@/types/events'
import type { NodeStatus } from '@/types/enums'
import type { PlanStep } from '@/types/plan'

interface WorkflowState {
  taskId: string | null
  selectedStep: PlanStep | null
  drawerOpen: boolean
  nodeStatuses: Record<string, NodeStatus>
  eventsByNode: Record<string, NodeEvent>
  lastSeq: number
  selectStep: (step: PlanStep | null) => void
  openDrawer: (step: PlanStep) => void
  closeDrawer: () => void
  reset: (taskId: string) => void
  applyEvent: (event: NodeEvent) => void
  getNodeEvent: (stepId: string) => NodeEvent | undefined
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  taskId: null,
  selectedStep: null,
  drawerOpen: false,
  nodeStatuses: {},
  eventsByNode: {},
  lastSeq: 0,

  selectStep: (step) => set({ selectedStep: step }),
  openDrawer: (step) => set({ selectedStep: step, drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),

  reset: (taskId) =>
    set({
      taskId,
      selectedStep: null,
      drawerOpen: false,
      nodeStatuses: {},
      eventsByNode: {},
      lastSeq: 0,
    }),

  applyEvent: (event) => {
    set((state) => ({
      taskId: event.task_id,
      nodeStatuses: {
        ...state.nodeStatuses,
        [event.node]: event.status,
      },
      eventsByNode: {
        ...state.eventsByNode,
        [event.node]: event,
      },
      lastSeq: Math.max(state.lastSeq, event.seq),
    }))
  },

  getNodeEvent: (stepId) => get().eventsByNode[stepId],
}))
