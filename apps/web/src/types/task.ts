import type { OutputLanguage, TaskStatus } from './enums'

export interface TaskPermissions {
  allow_web_search: boolean
  allow_repo_clone: boolean
  allow_smoke_test: boolean
  allow_dependency_install: boolean
  has_gpu: boolean
  max_runtime_minutes: number
}

export interface TaskCreateRequest {
  goal: string
  /** F-015：可选；留空则由 RepoDiscovery 自动发现热门相关仓库 */
  repo_urls?: string[]
  paper_urls?: string[]
  output_language?: OutputLanguage
  template?: string | null
  permissions?: TaskPermissions
}

export interface TaskResponse {
  task_id: string
  goal: string
  status: TaskStatus
  repo_urls: string[]
  paper_urls: string[]
  output_language: OutputLanguage
  template: string | null
  permissions: TaskPermissions
  created_at: string
}

export interface TaskCreateResponse {
  task_id: string
  status: TaskStatus
}

export const DEFAULT_PERMISSIONS: TaskPermissions = {
  allow_web_search: false,
  allow_repo_clone: true,
  allow_smoke_test: false,
  allow_dependency_install: false,
  has_gpu: false,
  max_runtime_minutes: 30,
}
