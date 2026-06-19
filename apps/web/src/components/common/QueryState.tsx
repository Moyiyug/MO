import type { ReactNode } from 'react'
import { AlertCircle, Inbox, Loader2, PauseCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MOError } from '@/api/client'

interface EmptyAction {
  label: string
  onClick?: () => void
  href?: string
}

interface QueryStateProps {
  isLoading?: boolean
  isError?: boolean
  error?: Error | null
  isEmpty?: boolean
  emptyTitle?: string
  emptyDescription?: string
  /** 空状态下的操作按钮 */
  emptyAction?: EmptyAction
  /** 页面数据已加载但被逻辑阻塞（如 waiting_user 需审批） */
  isBlocked?: boolean
  blockedTitle?: string
  blockedDescription?: string
  blockedAction?: { label: string; onClick: () => void }
  onRetry?: () => void
  children: ReactNode
}

function formatError(error: Error): string {
  if (error instanceof MOError) {
    if (typeof error.detail === 'string') return error.detail
    if (Array.isArray(error.detail)) {
      return error.detail
        .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
        .join('; ')
    }
    return error.message
  }
  return error.message
}

export function QueryState({
  isLoading,
  isError,
  error,
  isEmpty,
  emptyTitle = '暂无数据',
  emptyDescription,
  emptyAction,
  isBlocked,
  blockedTitle = '等待确认',
  blockedDescription,
  blockedAction,
  onRetry,
  children,
}: QueryStateProps) {
  if (isLoading) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        <span>加载中…</span>
      </div>
    )
  }

  if (isError && error) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 py-16 text-destructive"
        role="alert"
      >
        <AlertCircle className="h-8 w-8" aria-hidden />
        <p className="max-w-md text-center text-sm">{formatError(error)}</p>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            重试
          </Button>
        )}
      </div>
    )
  }

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
        <Inbox className="h-8 w-8" aria-hidden />
        <p className="font-medium text-foreground">{emptyTitle}</p>
        {emptyDescription && (
          <p className="max-w-md text-center text-sm">{emptyDescription}</p>
        )}
        {emptyAction && (
          emptyAction.href ? (
            <Button variant="outline" size="sm" asChild>
              <a href={emptyAction.href}>{emptyAction.label}</a>
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={emptyAction.onClick}>
              {emptyAction.label}
            </Button>
          )
        )}
      </div>
    )
  }

  if (isBlocked) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 py-16"
        role="alert"
      >
        <PauseCircle className="h-8 w-8 text-amber-500" aria-hidden />
        <p className="font-medium text-amber-900">{blockedTitle}</p>
        {blockedDescription && (
          <p className="max-w-md text-center text-sm text-amber-700">
            {blockedDescription}
          </p>
        )}
        {blockedAction && (
          <Button size="sm" onClick={blockedAction.onClick}>
            {blockedAction.label}
          </Button>
        )}
      </div>
    )
  }

  return <>{children}</>
}
