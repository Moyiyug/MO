import type { ClaimLabel } from './enums'

export interface DimensionScore {
  dimension: string
  repo_url: string
  score: number
  rationale: string
  evidence_ids: string[]
  label: ClaimLabel
}

export interface RepoRanking {
  repo_url: string
  repo_name: string
  weighted_total: number
  per_dimension: Record<string, number>
}

export interface ComparisonMatrix {
  id: string
  task_id: string
  repo_urls: string[]
  dimensions: string[]
  weights: Record<string, number>
  scores: DimensionScore[]
  rankings: RepoRanking[]
  recommendation: string
  limitations: string[]
  recommendation_evidence_ids: string[]
  generated_at: string
}

export interface RecomputeComparisonRequest {
  weights: Record<string, number>
}
