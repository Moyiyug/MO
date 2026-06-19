import type { NodeStatus } from '@/types/enums'

/** MO_Frontend §7.3 — amber=待用户、blue=运行中、emerald=完成、red=失败、slate=待定/跳过 */
export const NODE_STYLE: Record<NodeStatus, string> = {
  pending: 'border-slate-300 bg-slate-50/80 text-slate-700',
  running:
    'border-blue-500 bg-[linear-gradient(90deg,rgba(239,246,255,0.95),rgba(219,234,254,0.95),rgba(239,246,255,0.95))] text-blue-900 mo-node-running',
  waiting_user:
    'border-amber-500 bg-amber-50/95 text-amber-950 ring-1 ring-amber-300 mo-node-waiting',
  completed: 'border-emerald-400 bg-emerald-50/90 text-emerald-900',
  failed: 'border-red-500 bg-red-50/90 text-red-900',
  skipped: 'border-slate-200 bg-slate-100/70 text-slate-500 opacity-70',
}

export const TASK_STATUS_STYLE: Record<string, string> = {
  CREATED: 'bg-slate-100/80 text-slate-700 border-slate-300',
  PLANNING: 'bg-blue-50/90 text-blue-900 border-blue-300',
  WAITING_USER_CLARIFICATION:
    'bg-amber-50/95 text-amber-950 border-amber-500 ring-1 ring-amber-300 mo-node-waiting',
  WAITING_USER_APPROVAL:
    'bg-amber-50/95 text-amber-950 border-amber-500 ring-1 ring-amber-300 mo-node-waiting',
  PLAN_APPROVED: 'bg-emerald-50/90 text-emerald-900 border-emerald-400',
  EXECUTING: 'bg-blue-50/90 text-blue-900 border-blue-400 mo-node-running',
  REPLANNING: 'bg-blue-50/90 text-blue-900 border-blue-300',
  REPORT_DRAFT: 'bg-violet-50/90 text-violet-900 border-violet-300',
  REVIEW_REQUIRED:
    'bg-amber-50/95 text-amber-950 border-amber-500 ring-1 ring-amber-300 mo-node-waiting',
  DONE: 'bg-emerald-50/90 text-emerald-900 border-emerald-400',
  FAILED: 'bg-red-50/90 text-red-900 border-red-500',
}

// NODE_STATUS_LABEL 已废弃 — 文案统一从 @/lib/uiCopy 的 NODE_STATUS_COPY 获取
