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
  TaskBulkDeleteResponse,
  TaskCreateRequest,
  TaskCreateResponse,
  TaskPageResponse,
  TaskResponse,
} from '@/types'

import { api } from './client'

export const taskKeys = {
  all: ['tasks'] as const,
  pages: ['tasks', 'page'] as const,
  page: (limit: number, offset: number) => ['tasks', 'page', limit, offset] as const,
  detail: (id: string) => ['task', id] as const,
  plan: (id: string) => ['plan', id] as const,
}

export function fetchTask(taskId: string): Promise<TaskResponse> {
  return api<TaskResponse>(`/api/tasks/${taskId}`)
}

export function fetchTasks(): Promise<TaskResponse[]> {
  return api<TaskResponse[]>('/api/tasks')
}

export function fetchTaskPage(limit: number, offset: number): Promise<TaskPageResponse> {
  return api<TaskPageResponse>(`/api/tasks/page?limit=${limit}&offset=${offset}`)
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

export function rerunTask(taskId: string): Promise<TaskCreateResponse> {
  return api<TaskCreateResponse>(`/api/tasks/${taskId}/rerun`, {
    method: 'POST',
  })
}

export function deleteTask(taskId: string): Promise<void> {
  return api<void>(`/api/tasks/${taskId}`, {
    method: 'DELETE',
  })
}

export function deleteAllTasks(): Promise<TaskBulkDeleteResponse> {
  return api<TaskBulkDeleteResponse>('/api/tasks', {
    method: 'DELETE',
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

export function useTaskPage(limit: number, offset: number) {
  return useQuery({
    queryKey: taskKeys.page(limit, offset),
    queryFn: () => fetchTaskPage(limit, offset),
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

export function useRerunTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: rerunTask,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: taskKeys.all })
    },
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTask,
    onSuccess: (_data, taskId) => {
      void qc.invalidateQueries({ queryKey: taskKeys.all })
      void qc.invalidateQueries({ queryKey: taskKeys.pages })
      void qc.removeQueries({ queryKey: taskKeys.detail(taskId) })
      void qc.removeQueries({ queryKey: taskKeys.plan(taskId) })
    },
  })
}

export function useDeleteAllTasks() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAllTasks,
    onSuccess: (result) => {
      void qc.invalidateQueries({ queryKey: taskKeys.all })
      void qc.invalidateQueries({ queryKey: taskKeys.pages })
      for (const taskId of result.deleted_task_ids) {
        void qc.removeQueries({ queryKey: taskKeys.detail(taskId) })
        void qc.removeQueries({ queryKey: taskKeys.plan(taskId) })
      }
    },
  })
}
