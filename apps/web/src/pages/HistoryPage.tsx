import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { useSeedDemo } from '@/api/demo'
import { useRerunTask, useTasks } from '@/api/tasks'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { QueryState } from '@/components/common/QueryState'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import type { TaskResponse } from '@/types'

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

function taskDetailPath(task: TaskResponse): string {
  const base = `/tasks/${task.task_id}`
  if (task.status === 'DONE' || task.status === 'REVIEW_REQUIRED') {
    return `${base}/report`
  }
  if (
    task.status === 'EXECUTING' ||
    task.status === 'REPORT_DRAFT' ||
    task.status === 'FAILED'
  ) {
    return `${base}/workflow`
  }
  return `${base}/plan`
}

/** P-009 ProjectHistory（F-013） */
export function HistoryPage() {
  const navigate = useNavigate()
  const { data: tasks, isLoading, isError, error, refetch } = useTasks()
  const rerun = useRerunTask()
  const seedDemo = useSeedDemo()

  const handleSeedDemo = async () => {
    try {
      const created = await seedDemo.mutateAsync()
      toast.success('示例任务已加载')
      navigate(`/tasks/${created.task_id}/report`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载示例失败')
    }
  }

  const handleRerun = async (taskId: string) => {
    try {
      const created = await rerun.mutateAsync(taskId)
      toast.success('已克隆任务，进入计划阶段')
      navigate(`/tasks/${created.task_id}/plan`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '重开失败')
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">项目历史</h1>
          <p className="text-sm text-muted-foreground">
            查看过往任务、报告与证据；可克隆输入重新调研（F-013）。
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={seedDemo.isPending}
            onClick={() => void handleSeedDemo()}
          >
            加载示例任务
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/">新建任务</Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务列表</CardTitle>
          <CardDescription>按创建时间倒序</CardDescription>
        </CardHeader>
        <CardContent>
          <QueryState
            isLoading={isLoading}
            isError={isError}
            error={error}
            onRetry={() => void refetch()}
            isEmpty={!tasks || tasks.length === 0}
            emptyTitle="暂无历史任务"
            emptyDescription="创建第一个调研任务后，将在此显示。"
          >
            {tasks && tasks.length > 0 && (
              <ul className="divide-y">
                {tasks.map((task) => (
                  <li
                    key={task.task_id}
                    className="flex flex-wrap items-start justify-between gap-3 py-4 first:pt-0 last:pb-0"
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <Link
                        to={taskDetailPath(task)}
                        className="font-medium hover:underline"
                      >
                        {task.goal}
                      </Link>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <TaskStatusBadge status={task.status} />
                        <span>{formatDate(task.created_at)}</span>
                        <span>{task.repo_urls.length} 个仓库</span>
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <Link to={taskDetailPath(task)}>打开</Link>
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={rerun.isPending}
                        onClick={() => void handleRerun(task.task_id)}
                      >
                        重开
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  )
}
