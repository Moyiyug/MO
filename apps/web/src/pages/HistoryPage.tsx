import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Archive,
  ChevronLeft,
  ChevronRight,
  FolderGit2,
  RotateCcw,
  ShieldCheck,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'

import { useSeedDemo } from '@/api/demo'
import { useDeleteAllTasks, useDeleteTask, useRerunTask, useTaskPage } from '@/api/tasks'
import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { QueryState } from '@/components/common/QueryState'
import { StatusGuide } from '@/components/common/StatusGuide'
import { PageLayout, PrimaryWorkArea } from '@/components/common/InfoHierarchy'
import { PageCommandBar } from '@/components/common/PageCommandBar'
import { MetricChip } from '@/components/common/visual'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PAGE_GUIDE_COPY, CTA_COPY, DESTRUCTIVE_CONFIRM_COPY } from '@/lib/uiCopy'
import type { TaskResponse } from '@/types'

const PAGE_SIZE = 10

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

function nextStepLabel(status: string): string {
  if (status === 'WAITING_USER_CLARIFICATION' || status === 'WAITING_USER_APPROVAL') return '下一步：审阅计划'
  if (status === 'PLAN_APPROVED') return '下一步：开始执行'
  if (status === 'EXECUTING') return '执行中'
  if (status === 'REPORT_DRAFT' || status === 'REVIEW_REQUIRED') return '下一步：审阅报告'
  if (status === 'DONE') return '已完成'
  if (status === 'FAILED') return '执行失败'
  return ''
}

function outputLanguageLabel(task: TaskResponse): string {
  return task.output_language === 'en' ? 'English' : '中文'
}

function permissionSummary(task: TaskResponse): string {
  const enabled = [
    task.permissions.allow_web_search && '联网',
    task.permissions.allow_repo_clone && '克隆',
    task.permissions.allow_smoke_test && '冒烟测试',
    task.permissions.allow_dependency_install && '依赖安装',
  ].filter(Boolean)

  return enabled.length > 0 ? enabled.join(' / ') : '默认保守'
}

/** P-009 ProjectHistory — 历史任务管理 */
export function HistoryPage() {
  const navigate = useNavigate()
  const [deleteTarget, setDeleteTarget] = useState<TaskResponse | null>(null)
  const [deleteAllOpen, setDeleteAllOpen] = useState(false)
  const [page, setPage] = useState(0)
  const { data: taskPage, isLoading, isError, error, refetch } = useTaskPage(
    PAGE_SIZE,
    page * PAGE_SIZE,
  )
  const rerun = useRerunTask()
  const deleteTask = useDeleteTask()
  const deleteAllTasks = useDeleteAllTasks()
  const seedDemo = useSeedDemo()

  const tasks = taskPage?.items ?? []
  const total = taskPage?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const isEmpty = total === 0

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

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTask.mutateAsync(deleteTarget.task_id)
      toast.success('历史记录已删除')
      if (tasks.length === 1 && page > 0) {
        setPage((p) => Math.max(0, p - 1))
      }
      setDeleteTarget(null)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '删除失败')
    }
  }

  const handleConfirmDeleteAll = async () => {
    try {
      const result = await deleteAllTasks.mutateAsync()
      toast.success(
        result.skipped_task_ids.length > 0
          ? `已删除 ${result.deleted_task_ids.length} 条，跳过 ${result.skipped_task_ids.length} 条执行中任务`
          : `已删除 ${result.deleted_task_ids.length} 条历史记录`,
      )
      setDeleteAllOpen(false)
      setPage(0)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批量删除失败')
    }
  }

  const guide = PAGE_GUIDE_COPY.history

  return (
    <div className="mo-page-shell">
      <StatusGuide
        title={guide.title}
        whatNow={isEmpty ? guide.empty : guide.whatNow}
        primaryAction={
          isEmpty
            ? { label: CTA_COPY.create, href: '/' }
            : { label: CTA_COPY.create, href: '/' }
        }
        secondaryActions={
          isEmpty
            ? [{ label: CTA_COPY.loadDemo, onClick: () => void handleSeedDemo() }]
            : undefined
        }
      />

      <PageCommandBar
        position="top"
        title={isEmpty ? '还没有历史任务' : `共 ${total} 条历史任务`}
        description="每页最多 10 条；执行中的任务不会被批量删除。"
        secondary={[
          { label: CTA_COPY.loadDemo, onClick: () => void handleSeedDemo() },
          {
            label: '删除所有历史',
            onClick: () => setDeleteAllOpen(true),
            destructive: true,
            disabled: isEmpty || deleteAllTasks.isPending,
            icon: <Trash2 className="h-4 w-4" aria-hidden />,
          },
        ]}
      />

      <PageLayout>
        <PrimaryWorkArea>
          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle>任务列表</CardTitle>
                <CardDescription>
                  按创建时间倒序，第 {Math.min(page + 1, totalPages)} / {totalPages} 页
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0 || isLoading}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft />
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page + 1 >= totalPages || isLoading}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                  <ChevronRight />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <QueryState
                isLoading={isLoading}
                isError={isError}
                error={error}
                onRetry={() => void refetch()}
                isEmpty={isEmpty}
                emptyTitle={PAGE_GUIDE_COPY.history.empty}
                emptyDescription="创建第一个调研任务后，将在此显示。"
                emptyAction={{ label: CTA_COPY.create, href: '/' }}
              >
                {tasks.length > 0 && (
                  <ul className="space-y-3">
                    {tasks.map((task) => {
                      const isDeletingThis =
                        deleteTask.isPending &&
                        deleteTarget?.task_id === task.task_id
                      const isExecuting = task.status === 'EXECUTING'
                      return (
                        <li
                          key={task.task_id}
                          className="rounded-lg border bg-background/72 p-4 shadow-[var(--mo-shadow-line)] transition-colors hover:border-blue-300/80"
                        >
                          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0 flex-1 space-y-3">
                              <div className="flex min-w-0 gap-3">
                                <div className="mt-0.5 hidden h-9 w-9 shrink-0 items-center justify-center rounded-md border border-blue-200 bg-blue-50 text-blue-800 sm:flex">
                                  <Archive className="h-4 w-4" aria-hidden />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <Link
                                    to={taskDetailPath(task)}
                                    className="line-clamp-2 break-words font-medium hover:text-blue-800 hover:underline"
                                  >
                                    {task.goal}
                                  </Link>
                                  <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <TaskStatusBadge status={task.status} />
                                    {nextStepLabel(task.status) && (
                                      <MetricChip
                                        label={nextStepLabel(task.status)}
                                        tone={
                                          task.status === 'FAILED'
                                            ? 'red'
                                            : task.status === 'DONE'
                                              ? 'green'
                                              : 'blue'
                                        }
                                      />
                                    )}
                                    <MetricChip label={formatDate(task.created_at)} tone="slate" />
                                  </div>
                                </div>
                              </div>

                              <div className="flex flex-wrap gap-2">
                                <MetricChip
                                  label="仓库"
                                  value={task.repo_urls.length}
                                  tone={task.repo_urls.length > 0 ? 'blue' : 'slate'}
                                  icon={<FolderGit2 className="h-3.5 w-3.5" aria-hidden />}
                                />
                                <MetricChip label={outputLanguageLabel(task)} tone="violet" />
                                <MetricChip
                                  label={permissionSummary(task)}
                                  tone={permissionSummary(task) === '默认保守' ? 'green' : 'amber'}
                                  icon={<ShieldCheck className="h-3.5 w-3.5" aria-hidden />}
                                />
                                {task.template && <MetricChip label={task.template} tone="slate" />}
                              </div>

                              {isExecuting && (
                                <p className="text-xs text-amber-700">
                                  执行中的任务会保留现场，暂不可删除。
                                </p>
                              )}
                            </div>

                            <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                              {isDeletingThis ? (
                                <Button variant="outline" size="sm" disabled>
                                  打开
                                </Button>
                              ) : (
                                <Button variant="outline" size="sm" asChild>
                                  <Link to={taskDetailPath(task)}>打开</Link>
                                </Button>
                              )}
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={rerun.isPending || isDeletingThis}
                                onClick={() => void handleRerun(task.task_id)}
                              >
                                <RotateCcw className="h-4 w-4" aria-hidden />
                                {CTA_COPY.redo}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isDeletingThis || isExecuting}
                                title={
                                  isExecuting
                                    ? DESTRUCTIVE_CONFIRM_COPY.deleteExecutingBlocked.description
                                    : '删除历史记录'
                                }
                                onClick={() => setDeleteTarget(task)}
                              >
                                <Trash2 className="h-4 w-4" aria-hidden />
                                {CTA_COPY.delete}
                              </Button>
                            </div>
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </QueryState>
            </CardContent>
          </Card>
        </PrimaryWorkArea>
      </PageLayout>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleteTask.isPending) setDeleteTarget(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{DESTRUCTIVE_CONFIRM_COPY.deleteTask.title}</DialogTitle>
            <DialogDescription>
              {DESTRUCTIVE_CONFIRM_COPY.deleteTask.description}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            {deleteTarget?.goal}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={deleteTask.isPending}
              onClick={() => setDeleteTarget(null)}
            >
              {CTA_COPY.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteTask.isPending}
              onClick={() => void handleConfirmDelete()}
            >
              <Trash2 />
              {DESTRUCTIVE_CONFIRM_COPY.deleteTask.confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteAllOpen}
        onOpenChange={(open) => {
          if (!open && !deleteAllTasks.isPending) setDeleteAllOpen(false)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除所有历史记录</DialogTitle>
            <DialogDescription>
              将删除所有非执行中的历史任务及其本地任务数据；执行中任务会被保留。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            当前共有 {total} 条历史记录。
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={deleteAllTasks.isPending}
              onClick={() => setDeleteAllOpen(false)}
            >
              {CTA_COPY.cancel}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteAllTasks.isPending}
              onClick={() => void handleConfirmDeleteAll()}
            >
              <Trash2 />
              确认删除所有可删除任务
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
