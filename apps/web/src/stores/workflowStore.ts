import { create } from 'zustand'

import type { PlanStep } from '@/types/plan'

interface WorkflowState {
  selectedStep: PlanStep | null
  drawerOpen: boolean
  selectStep: (step: PlanStep | null) => void
  openDrawer: (step: PlanStep) => void
  closeDrawer: () => void
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  selectedStep: null,
  drawerOpen: false,
  selectStep: (step) => set({ selectedStep: step }),
  openDrawer: (step) => set({ selectedStep: step, drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),
}))
