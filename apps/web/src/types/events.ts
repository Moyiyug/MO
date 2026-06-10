import type { NodeStatus } from './enums'

/** PRD F-010 — M4 SSE 事件契约（本期预留类型） */
export interface NodeEvent {
  node: string
  status: NodeStatus
  input_summary?: string | null
  output_summary?: string | null
  evidence_ids?: string[]
  logs?: string[]
  error_message?: string | null
  next_action?: string | null
}
