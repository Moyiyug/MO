import { useParams } from 'react-router-dom'

import { useTask } from '@/api/tasks'
import { QueryState } from '@/components/common/QueryState'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { Card, CardContent } from '@/components/ui/card'

/** P-007 Report — M7 前仅骨架 + empty 态 */
export function ReportPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task, isLoading, isError, error, refetch } = useTask(taskId)

  const hasReport =
    task?.status === 'REPORT_DRAFT' ||
    task?.status === 'REVIEW_REQUIRED' ||
    task?.status === 'DONE'

  return (
    <QueryState
      isLoading={isLoading}
      isError={isError}
      error={error}
      onRetry={() => void refetch()}
      isEmpty={!hasReport}
      emptyTitle="报告尚未生成"
      emptyDescription="报告将在执行阶段完成后生成（M7）。本页已预置安全 Markdown 渲染能力。"
    >
      {task && hasReport && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold">调研报告</h1>
            <TaskStatusBadge status={task.status} />
          </div>
          <Card>
            <CardContent className="pt-6">
              <SafeMarkdown markdown="# 报告占位\n\n待 M7 接入后端报告 API。" />
            </CardContent>
          </Card>
        </div>
      )}
    </QueryState>
  )
}
