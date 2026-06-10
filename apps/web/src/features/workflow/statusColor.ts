import type { NodeStatus } from '@/types/enums'

/** MO_Frontend §7.3 — amber=待用户、blue=运行中、emerald=完成、red=失败、slate=待定/跳过 */
export const NODE_STYLE: Record<NodeStatus, string> = {
  pending: 'border-slate-300 bg-slate-50 text-slate-700',
  running: 'border-blue-400 bg-blue-50 text-blue-800 animate-pulse',
  waiting_user:
    'border-amber-500 bg-amber-50 text-amber-900 ring-2 ring-amber-400',
  completed: 'border-emerald-400 bg-emerald-50 text-emerald-800',
  failed: 'border-red-500 bg-red-50 text-red-800',
  skipped: 'border-slate-200 bg-slate-100 text-slate-500 opacity-60',
}

export const TASK_STATUS_STYLE: Record<string, string> = {
  CREATED: 'bg-slate-100 text-slate-700 border-slate-300',
  PLANNING: 'bg-blue-50 text-blue-800 border-blue-300',
  WAITING_USER_CLARIFICATION:
    'bg-amber-50 text-amber-900 border-amber-500 ring-2 ring-amber-400',
  WAITING_USER_APPROVAL:
    'bg-amber-50 text-amber-900 border-amber-500 ring-2 ring-amber-400',
  PLAN_APPROVED: 'bg-emerald-50 text-emerald-800 border-emerald-400',
  EXECUTING: 'bg-blue-50 text-blue-800 border-blue-400 animate-pulse',
  REPLANNING: 'bg-blue-50 text-blue-800 border-blue-300',
  REPORT_DRAFT: 'bg-violet-50 text-violet-800 border-violet-300',
  REVIEW_REQUIRED:
    'bg-amber-50 text-amber-900 border-amber-500 ring-2 ring-amber-400',
  DONE: 'bg-emerald-50 text-emerald-800 border-emerald-400',
  FAILED: 'bg-red-50 text-red-800 border-red-500',
}

export const NODE_STATUS_LABEL: Record<NodeStatus, string> = {
  pending: '待定',
  running: '运行中',
  waiting_user: '等待用户',
  completed: '已完成',
  failed: '失败',
  skipped: '已跳过',
}
