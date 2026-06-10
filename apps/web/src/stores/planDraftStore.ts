import { create } from 'zustand'

import { DEFAULT_RUBRIC_WEIGHTS } from '@/types/plan'
import type { ClarifyingQuestion, Plan, PlanStep } from '@/types/plan'

interface PlanDraftState {
  rubricWeights: Record<string, number>
  disabledStepIds: Set<string>
  clarificationAnswers: Record<string, string>
  initializedForPlanId: string | null
  initFromPlan: (plan: Plan) => void
  setRubricWeight: (key: string, value: number) => void
  toggleStep: (stepId: string) => void
  setClarificationAnswer: (questionId: string, answer: string) => void
  reset: () => void
}

export const usePlanDraftStore = create<PlanDraftState>((set, get) => ({
  rubricWeights: { ...DEFAULT_RUBRIC_WEIGHTS },
  disabledStepIds: new Set<string>(),
  clarificationAnswers: {},
  initializedForPlanId: null,

  initFromPlan: (plan: Plan) => {
    if (get().initializedForPlanId === plan.id) return
    const answers: Record<string, string> = {}
    for (const q of plan.clarifying_questions) {
      if (q.answer) answers[q.id] = q.answer
    }
    set({
      rubricWeights: { ...plan.report_rubric.weights },
      disabledStepIds: new Set(
        plan.proposed_steps
          .filter((s) => s.status === 'skipped')
          .map((s) => s.id),
      ),
      clarificationAnswers: answers,
      initializedForPlanId: plan.id,
    })
  },

  setRubricWeight: (key, value) => {
    set((s) => ({
      rubricWeights: { ...s.rubricWeights, [key]: value },
    }))
  },

  toggleStep: (stepId) => {
    set((s) => {
      const next = new Set(s.disabledStepIds)
      if (next.has(stepId)) next.delete(stepId)
      else next.add(stepId)
      return { disabledStepIds: next }
    })
  },

  setClarificationAnswer: (questionId, answer) => {
    set((s) => ({
      clarificationAnswers: {
        ...s.clarificationAnswers,
        [questionId]: answer,
      },
    }))
  },

  reset: () =>
    set({
      rubricWeights: { ...DEFAULT_RUBRIC_WEIGHTS },
      disabledStepIds: new Set(),
      clarificationAnswers: {},
      initializedForPlanId: null,
    }),
}))

export function isStepEnabled(
  step: PlanStep,
  disabledIds: Set<string>,
): boolean {
  return !disabledIds.has(step.id) && step.status !== 'skipped'
}

export function unansweredRequired(
  questions: ClarifyingQuestion[],
  answers: Record<string, string>,
): ClarifyingQuestion[] {
  return questions.filter((q) => q.required && !answers[q.id]?.trim())
}
