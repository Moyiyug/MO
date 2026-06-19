import { Link, Outlet, useParams } from 'react-router-dom'

import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { useTask } from '@/api/tasks'
import { cn } from '@/lib/utils'

const NAV = [
  { to: 'plan', label: '计划审阅' },
  { to: 'workflow', label: '工作流' },
  { to: 'comparison', label: '对比' },
  { to: 'report', label: '报告' },
] as const

export function AppLayout() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task } = useTask(taskId)

  return (
    <div className="min-h-svh flex flex-col">
      <header className="sticky top-0 z-40 border-b border-[var(--mo-line)] bg-background/86 shadow-[var(--mo-shadow-line)] backdrop-blur supports-[backdrop-filter]:bg-background/72">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <Link to="/" className="text-lg font-semibold tracking-[0.18em] text-blue-900">
              MO
            </Link>
            <Link
              to="/history"
              className="rounded-md px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-blue-50 hover:text-blue-800"
            >
              历史
            </Link>
            {taskId && (
              <span className="max-w-28 truncate text-xs text-muted-foreground" title={taskId}>
                任务 {taskId.slice(0, 8)}…
              </span>
            )}
            {task && <TaskStatusBadge status={task.status} />}
          </div>
          {taskId && (
            <nav className="-mx-1 flex max-w-full gap-1 overflow-x-auto px-1" aria-label="任务导航">
              {NAV.map(({ to, label }) => (
                <Link
                  key={to}
                  to={`/tasks/${taskId}/${to}`}
                  className={cn(
                    'rounded-md border border-transparent px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-800',
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 pb-24">
        <Outlet />
      </main>
    </div>
  )
}
