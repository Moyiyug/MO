import type { EvidenceStrength, SourceType } from './enums'

export interface EvidenceItem {
  id: string
  task_id: string
  source_type: SourceType
  source_uri: string
  locator?: string | null
  quote_or_summary: string
  strength: EvidenceStrength
  material_type?: string | null
  used_by: string[]
  created_at: string
}
