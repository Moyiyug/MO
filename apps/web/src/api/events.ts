import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'
import { taskKeys } from '@/api/tasks'
import type {
  ExecuteResponse,
  NodeEvent,
  StepApproveResponse,
} from '@/types/events'
import { getApiBaseUrl } from '@/api/client'

export function startExecution(taskId: string): Promise<ExecuteResponse> {
  return api<ExecuteResponse>(`/api/tasks/${taskId}/execute`, {
    method: 'POST',
  })
}

export function approveStep(
  taskId: string,
  stepId: string,
  approved: boolean,
): Promise<StepApproveResponse> {
  return api<StepApproveResponse>(
    `/api/tasks/${taskId}/steps/${stepId}/approve`,
    {
      method: 'POST',
      body: JSON.stringify({ approved }),
    },
  )
}

export function subscribeEvents(
  taskId: string,
  onEvent: (event: NodeEvent) => void,
  options?: { since?: number; onError?: () => void },
): () => void {
  const base = getApiBaseUrl()
  const since = options?.since ?? 0
  const url = `${base}/api/tasks/${taskId}/events?since=${since}`
  const es = new EventSource(url)

  es.addEventListener('node', (message) => {
    try {
      const event = JSON.parse(message.data) as NodeEvent
      onEvent(event)
    } catch {
      options?.onError?.()
    }
  })

  es.onerror = () => {
    es.close()
    options?.onError?.()
  }

  return () => es.close()
}

export function useStartExecution() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startExecution,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}

export function useApproveStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      stepId,
      approved,
    }: {
      taskId: string
      stepId: string
      approved: boolean
    }) => approveStep(taskId, stepId, approved),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}
