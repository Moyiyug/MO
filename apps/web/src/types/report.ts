import type { ClaimLabel } from './enums'

export interface ReportClaim {
  id: string
  claim: string
  label: ClaimLabel
  confidence?: number
  evidence_ids: string[]
  requires_user_review?: boolean
}

export interface ReportSectionMetadata {
  structured_markdown?: string
  seed_narratives?: string[]
  seed_structured_data?: unknown[]
  seed_nodes?: string[]
  seed_warnings?: string[]
  polish_status?: 'polished' | 'fallback' | 'failed' | 'not_polished' | string
  polish_warnings?: string[]
  node_events?: unknown[]
  plan_steps?: unknown[]
  [key: string]: unknown
}

export interface ReportSection {
  key: string
  title: string
  markdown: string
  claims: ReportClaim[]
  is_pending?: boolean
  // Report v2 optional fields
  summary?: string
  evidence_ids?: string[]
  metadata?: ReportSectionMetadata
  structured_markdown?: string
  polish_status?: string
}

export interface KeyFinding {
  title: string
  summary: string
  label: ClaimLabel
  evidence_ids: string[]
  requires_user_review: boolean
}

export interface ScenarioRecommendation {
  scenario: string
  recommendation: string
  rationale: string
  label: ClaimLabel
  evidence_ids: string[]
  requires_user_review: boolean
}

export interface EvidenceAppendixGroup {
  key: string
  title: string
  evidence_ids: string[]
}

export interface ReportResponse {
  id: string
  task_id: string
  sections: ReportSection[]
  pending_warnings: string[]
  generated_at: string
  markdown: string
  // Report v2 optional fields
  executive_summary?: string
  key_findings?: KeyFinding[]
  recommendation_summary?: ScenarioRecommendation[]
  evidence_appendix_groups?: EvidenceAppendixGroup[]
  report_version?: string
}
