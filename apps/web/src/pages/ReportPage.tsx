import { useParams } from 'react-router-dom'

import { useTask } from '@/api/tasks'
import { ClaimLabel } from '@/components/common/ClaimLabel'
import { QueryState } from '@/components/common/QueryState'
import { SafeMarkdown } from '@/components/common/SafeMarkdown'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

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
      emptyDescription="报告将在执行阶段完成后生成（M7）。当前可预览 claim 标签组件与安全 Markdown 渲染能力。"
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

/** 演示 claim 标签与安全渲染 — empty 态下方展示 */
export function ReportPreviewDemo() {
  return (
    <Card className="mt-6 border-dashed">
      <CardHeader>
        <CardTitle className="text-base">组件预览</CardTitle>
        <CardDescription>
          Claim 标签与 Markdown sanitize 预置（P-007 / R-003）
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <ClaimLabel label="fact" />
          <ClaimLabel label="inference" />
          <ClaimLabel label="recommendation" />
          <ClaimLabel label="pending" />
        </div>
        <SafeMarkdown
          markdown={`## 示例段落

- **事实**：仓库 README 存在安装说明
- **推断**：入口可能在 \`main.py\`
- **待定**：复现结果待 run log 确认

<script>alert('xss')</script>`}
          className="prose prose-sm max-w-none rounded-md border bg-muted/30 p-4"
        />
      </CardContent>
    </Card>
  )
}
