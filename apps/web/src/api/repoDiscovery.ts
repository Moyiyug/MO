import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  RepoCandidateListResponse,
  RepoCandidateSelectRequest,
} from '@/types'

import { api } from './client'
import { taskKeys } from './tasks'

export const repoCandidateKeys = {
  list: (id: string) => ['repo-candidates', id] as const,
}

export function fetchRepoCandidates(
  taskId: string,
): Promise<RepoCandidateListResponse> {
  return api<RepoCandidateListResponse>(`/api/tasks/${taskId}/repo-candidates`)
}

export function selectRepoCandidates(
  taskId: string,
  payload: RepoCandidateSelectRequest,
): Promise<RepoCandidateListResponse> {
  return api<RepoCandidateListResponse>(
    `/api/tasks/${taskId}/repo-candidates`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function useRepoCandidates(taskId: string | undefined) {
  return useQuery({
    queryKey: repoCandidateKeys.list(taskId ?? ''),
    queryFn: () => fetchRepoCandidates(taskId!),
    enabled: Boolean(taskId),
  })
}

export function useSelectRepoCandidates() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: RepoCandidateSelectRequest
    }) => selectRepoCandidates(taskId, payload),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: repoCandidateKeys.list(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.plan(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}
