import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'

import type {
  ComparisonMatrix,
  RecomputeComparisonRequest,
} from '@/types/comparison'

import { api } from './client'

export const comparisonKeys = {
  detail: (id: string) => ['comparison', id] as const,
}

export function fetchComparison(taskId: string): Promise<ComparisonMatrix> {
  return api<ComparisonMatrix>(`/api/tasks/${taskId}/comparison`)
}

export function recomputeComparison(
  taskId: string,
  payload: RecomputeComparisonRequest,
): Promise<ComparisonMatrix> {
  return api<ComparisonMatrix>(`/api/tasks/${taskId}/comparison`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function useComparison(
  taskId: string | undefined,
  enabled: boolean,
  options?: Omit<UseQueryOptions<ComparisonMatrix>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: comparisonKeys.detail(taskId ?? ''),
    queryFn: () => fetchComparison(taskId!),
    enabled: Boolean(taskId) && enabled,
    retry: false,
    ...options,
  })
}

export function useRecomputeWeights() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: RecomputeComparisonRequest
    }) => recomputeComparison(taskId, payload),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: comparisonKeys.detail(taskId) })
    },
  })
}
