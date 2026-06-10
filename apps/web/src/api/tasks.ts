import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query'

import type {
  ApprovePlanRequest,
  ApprovePlanResponse,
  ClarificationsRequest,
  Plan,
  ReplanRequest,
  TaskCreateRequest,
  TaskCreateResponse,
  TaskResponse,
} from '@/types'

import { api } from './client'

export const taskKeys = {
  all: ['tasks'] as const,
  detail: (id: string) => ['task', id] as const,
  plan: (id: string) => ['plan', id] as const,
}

export function fetchTask(taskId: string): Promise<TaskResponse> {
  return api<TaskResponse>(`/api/tasks/${taskId}`)
}

export function fetchTasks(): Promise<TaskResponse[]> {
  return api<TaskResponse[]>('/api/tasks')
}

export function createTask(
  payload: TaskCreateRequest,
): Promise<TaskCreateResponse> {
  return api<TaskCreateResponse>('/api/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchPlan(taskId: string): Promise<Plan> {
  return api<Plan>(`/api/tasks/${taskId}/plan`)
}

export function generatePlan(taskId: string): Promise<Plan> {
  return api<Plan>(`/api/tasks/${taskId}/plan`, { method: 'POST' })
}

export function submitClarifications(
  taskId: string,
  payload: ClarificationsRequest,
): Promise<Plan> {
  return api<Plan>(`/api/tasks/${taskId}/clarifications`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function approvePlan(
  taskId: string,
  payload: ApprovePlanRequest,
): Promise<ApprovePlanResponse> {
  return api<ApprovePlanResponse>(`/api/tasks/${taskId}/approve-plan`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function replan(taskId: string, payload: ReplanRequest): Promise<Plan> {
  return api<Plan>(`/api/tasks/${taskId}/replan`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function useTask(
  taskId: string | undefined,
  options?: Omit<UseQueryOptions<TaskResponse>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: taskKeys.detail(taskId ?? ''),
    queryFn: () => fetchTask(taskId!),
    enabled: Boolean(taskId),
    ...options,
  })
}

export function useTasks() {
  return useQuery({
    queryKey: taskKeys.all,
    queryFn: fetchTasks,
  })
}

export function usePlan(
  taskId: string | undefined,
  options?: Omit<UseQueryOptions<Plan>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: taskKeys.plan(taskId ?? ''),
    queryFn: () => fetchPlan(taskId!),
    enabled: Boolean(taskId),
    ...options,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: taskKeys.all })
    },
  })
}

export function useGeneratePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: generatePlan,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.plan(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}

export function useSubmitClarifications() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: ClarificationsRequest
    }) => submitClarifications(taskId, payload),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: taskKeys.plan(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}

export function useApprovePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: ApprovePlanRequest
    }) => approvePlan(taskId, payload),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: taskKeys.plan(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}

export function useReplan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      taskId,
      payload,
    }: {
      taskId: string
      payload: ReplanRequest
    }) => replan(taskId, payload),
    onSuccess: (_data, { taskId }) => {
      void qc.invalidateQueries({ queryKey: taskKeys.plan(taskId) })
      void qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) })
    },
  })
}
