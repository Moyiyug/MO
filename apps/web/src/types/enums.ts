/** 镜像 apps/api/mo_api/models/enums.py — 改一端必须同步另一端 */

export type TaskStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'WAITING_USER_CLARIFICATION'
  | 'WAITING_USER_APPROVAL'
  | 'PLAN_APPROVED'
  | 'EXECUTING'
  | 'REPLANNING'
  | 'REPORT_DRAFT'
  | 'REVIEW_REQUIRED'
  | 'DONE'
  | 'FAILED'

export type OutputLanguage = 'zh' | 'en'

export type NodeStatus =
  | 'pending'
  | 'running'
  | 'waiting_user'
  | 'completed'
  | 'failed'
  | 'skipped'

export type ClaimLabel =
  | 'fact'
  | 'inference'
  | 'recommendation'
  | 'pending'

export type EvidenceStrength = 'strong' | 'medium' | 'weak' | 'missing'

export type SourceType =
  | 'repo_file'
  | 'paper'
  | 'web'
  | 'run_log'
  | 'user_confirmation'
  | 'model_inference'

export type RiskLevel = 'low' | 'medium' | 'high'

export type PlanStepTool =
  | 'repo_ingest'
  | 'code_understanding'
  | 'paper_research'
  | 'repro_eval'
  | 'comparison'
  | 'critic_review'
  | 'report_writer'
  | 'sandbox_runner'

export type PlanStepStatus = 'pending' | 'approved' | 'skipped'

export const WAITING_USER_TASK_STATUSES: TaskStatus[] = [
  'WAITING_USER_CLARIFICATION',
  'WAITING_USER_APPROVAL',
]
