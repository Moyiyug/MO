/** 仓库自动发现类型（F-015），与后端 models/repo_discovery.py 保持一致 */

export type DiscoveredBy = 'github_search' | 'user_seed'

export interface RepoCandidate {
  repo_url: string
  repo_name: string
  description: string | null
  stars: number
  language: string | null
  pushed_at: string | null
  topics: string[]
  relevance_score: number
  relevance_reason: string
  selected: boolean
  discovered_by: DiscoveredBy
}

export interface RepoCandidateListResponse {
  task_id: string
  candidates: RepoCandidate[]
  discovery_note: string | null
}

export interface RepoCandidateSelectRequest {
  selected_repo_urls: string[]
}
