import { Link, Outlet, useParams } from 'react-router-dom'

import { TaskStatusBadge } from '@/components/common/StatusBadge'
import { useTask } from '@/api/tasks'
import { cn } from '@/lib/utils'

const NAV = [
  { to: 'plan', label: '计划审阅' },
  { to: 'workflow', label: '工作流' },
  { to: 'report', label: '报告' },
] as const

export function AppLayout() {
  const { taskId } = useParams<{ taskId: string }>()
  const { data: task } = useTask(taskId)

  return (
    <div className="min-h-svh flex flex-col">
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-lg font-semibold tracking-tight">
              MO
            </Link>
            {taskId && (
              <span className="text-sm text-muted-foreground">
                任务 {taskId.slice(0, 8)}…
              </span>
            )}
            {task && <TaskStatusBadge status={task.status} />}
          </div>
          {taskId && (
            <nav className="flex gap-1" aria-label="任务导航">
              {NAV.map(({ to, label }) => (
                <Link
                  key={to}
                  to={`/tasks/${taskId}/${to}`}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
