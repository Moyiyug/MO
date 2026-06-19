import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'

import type { ReportResponse } from '@/types/report'
import type { TaskResponse } from '@/types/task'

import { api, getApiBaseUrl } from './client'
import { taskKeys } from './tasks'

export const reportKeys = {
  detail: (id: string) => ['report', id] as const,
}

export function fetchReport(taskId: string): Promise<ReportResponse> {
  return api<ReportResponse>(`/api/tasks/${taskId}/report`)
}

export function generateReport(taskId: string): Promise<ReportResponse> {
  return api<ReportResponse>(`/api/tasks/${taskId}/generate-report`, {
    method: 'POST',
  })
}

export async function exportReport(taskId: string): Promise<void> {
  const base = getApiBaseUrl()
  const res = await fetch(`${base}/api/tasks/${taskId}/export`, {
    method: 'POST',
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = (await res.json()) as { detail?: string }
      detail = String(body.detail ?? detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mo-report-${taskId.slice(0, 8)}.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function confirmReport(
  taskId: string,
): Promise<{ task_id: string; status: string }> {
  return api<{ task_id: string; status: string }>(
    `/api/tasks/${taskId}/confirm-report`,
    { method: 'POST' },
  )
}

export function useReport(
  taskId: string | undefined,
  enabled: boolean,
  options?: Omit<UseQueryOptions<ReportResponse>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: reportKeys.detail(taskId ?? ''),
    queryFn: () => fetchReport(taskId!),
    enabled: Boolean(taskId) && enabled,
    ...options,
  })
}

export function useConfirmReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: confirmReport,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
      void qc.invalidateQueries({ queryKey: reportKeys.detail(taskId) })
    },
  })
}

export function useGenerateReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: generateReport,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
      void qc.invalidateQueries({ queryKey: reportKeys.detail(taskId) })
    },
  })
}

export function regenerateReport(
  taskId: string,
): Promise<ReportResponse> {
  return api<ReportResponse>(`/api/tasks/${taskId}/regenerate-report`, {
    method: 'POST',
  })
}

export function useRegenerateReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: regenerateReport,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
      void qc.invalidateQueries({ queryKey: reportKeys.detail(taskId) })
    },
  })
}

export function useExportReport() {
  return useMutation({
    mutationFn: exportReport,
  })
}

export type { TaskResponse }
