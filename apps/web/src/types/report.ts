import type { ClaimLabel, EvidenceStrength } from './enums'

export interface ReportClaim {
  id: string
  text: string
  label: ClaimLabel
  evidence_ids: string[]
  strength?: EvidenceStrength
}

/** M7 报告响应占位 — 本期 ReportPage 仅 empty 态 */
export interface ReportResponse {
  task_id: string
  markdown: string
  claims: ReportClaim[]
}
