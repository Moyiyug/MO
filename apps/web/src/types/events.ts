import type { NodeStatus } from './enums'

/** PRD F-010 — SSE 节点事件契约 */
export interface NodeEvent {
  task_id: string
  seq: number
  node: string
  status: NodeStatus
  input_summary?: string | null
  output_summary?: string | null
  evidence_ids?: string[]
  logs?: string[]
  error_message?: string | null
  next_action?: string | null
  created_at?: string
}

export interface ExecuteResponse {
  task_id: string
  status: string
}

export interface StepApproveResponse {
  task_id: string
  step_id: string
  status: string
}
