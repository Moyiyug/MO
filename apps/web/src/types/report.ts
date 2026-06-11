import type { ClaimLabel } from './enums'

export interface ReportClaim {
  id: string
  claim: string
  label: ClaimLabel
  confidence?: number
  evidence_ids: string[]
  requires_user_review?: boolean
}

export interface ReportSection {
  key: string
  title: string
  markdown: string
  claims: ReportClaim[]
  is_pending?: boolean
}

export interface ReportResponse {
  id: string
  task_id: string
  sections: ReportSection[]
  pending_warnings: string[]
  generated_at: string
  markdown: string
}
