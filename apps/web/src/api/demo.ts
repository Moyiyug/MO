import { useMutation } from '@tanstack/react-query'

import type { TaskCreateResponse } from '@/types'

import { api } from './client'

export function seedDemoTask(): Promise<TaskCreateResponse> {
  return api<TaskCreateResponse>('/api/demo/seed', { method: 'POST' })
}

export function useSeedDemo() {
  return useMutation({ mutationFn: seedDemoTask })
}
