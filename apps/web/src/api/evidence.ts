import { useQuery, type UseQueryOptions } from '@tanstack/react-query'

import type { EvidenceItem } from '@/types/evidence'

import { api } from './client'

export const evidenceKeys = {
  list: (taskId: string) => ['evidence', taskId] as const,
}

export function fetchEvidence(taskId: string): Promise<EvidenceItem[]> {
  return api<EvidenceItem[]>(`/api/tasks/${taskId}/evidence`)
}

export function useEvidence(
  taskId: string | undefined,
  enabled = true,
  options?: Omit<UseQueryOptions<EvidenceItem[]>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: evidenceKeys.list(taskId ?? ''),
    queryFn: () => fetchEvidence(taskId!),
    enabled: Boolean(taskId) && enabled,
    ...options,
  })
}
