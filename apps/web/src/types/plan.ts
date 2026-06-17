import type {
  PlanStepStatus,
  PlanStepTool,
  RiskLevel,
} from './enums'
import type { RepoCandidate } from './repoDiscovery'

export const DEFAULT_RUBRIC_WEIGHTS: Record<string, number> = {
  reproducibility: 0.3,
  documentation: 0.2,
  research_value: 0.2,
  engineering_fit: 0.2,
  extensibility: 0.1,
}

export interface ClarifyingQuestion {
  id: string
  question: string
  options: string[]
  answer: string | null
  required: boolean
}

export interface PlanStep {
  id: string
  node_id: string  // F-002: matches WorkflowNode in execute graph
  title: string
  description: string
  tool: PlanStepTool
  risk_level: RiskLevel
  requires_approval: boolean
  expected_outputs: string[]
  depends_on: string[]
  user_editable: boolean
  status: PlanStepStatus
}

export interface ReportRubric {
  weights: Record<string, number>
}

export interface Plan {
  id: string
  task_id: string
  task_summary: string
  confirmed_context: string[]
  unknowns: string[]
  clarifying_questions: ClarifyingQuestion[]
  proposed_steps: PlanStep[]
  report_rubric: ReportRubric
  risk_summary: string[]
  approval_required: boolean
  repo_candidates: RepoCandidate[]
  created_at: string
}

export interface ClarificationAnswer {
  question_id: string
  answer: string
}

export interface ClarificationsRequest {
  answers: ClarificationAnswer[]
}

export interface ApprovePlanRequest {
  rubric_weights?: Record<string, number> | null
  disabled_step_ids?: string[]
}

export interface ApprovePlanResponse {
  plan: Plan
  status: string
}

export interface ReplanRequest {
  reason?: string | null
}

export function rubricWeightsSum(weights: Record<string, number>): number {
  return Object.values(weights).reduce((a, b) => a + b, 0)
}

export function isRubricValid(weights: Record<string, number>): boolean {
  return Math.abs(rubricWeightsSum(weights) - 1.0) <= 0.01
}
