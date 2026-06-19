import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, Inbox, PauseCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MOError } from '@/api/client'
import { BlueprintEmptyState, BlueprintSkeleton } from '@/components/common/visual'

interface EmptyAction {
  label: string
  onClick?: () => void
  to?: string
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

function isInternalHref(href: string | undefined): href is string {
  return Boolean(href && href.startsWith('/'))
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
    return <BlueprintSkeleton className="my-12" lines={5} />
  }

  if (isError && error) {
    return (
      <BlueprintEmptyState
        title="加载失败"
        description={formatError(error)}
        icon={<AlertCircle className="h-5 w-5 text-red-700" aria-hidden />}
        action={
          onRetry ? (
            <Button variant="outline" size="sm" onClick={onRetry}>
              重试
            </Button>
          ) : undefined
        }
      />
    )
  }

  if (isEmpty) {
    return (
      <BlueprintEmptyState
        title={emptyTitle}
        description={emptyDescription}
        icon={<Inbox className="h-5 w-5" aria-hidden />}
        action={
          emptyAction ? (
            emptyAction.to || emptyAction.href ? (
              <Button variant="outline" size="sm" asChild>
                {emptyAction.to || isInternalHref(emptyAction.href) ? (
                  <Link to={emptyAction.to ?? emptyAction.href!}>
                    {emptyAction.label}
                  </Link>
                ) : (
                  <a href={emptyAction.href}>{emptyAction.label}</a>
                )}
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={emptyAction.onClick}>
                {emptyAction.label}
              </Button>
            )
          ) : undefined
        }
      />
    )
  }

  if (isBlocked) {
    return (
      <BlueprintEmptyState
        title={blockedTitle}
        description={blockedDescription}
        icon={<PauseCircle className="h-5 w-5 text-amber-600" aria-hidden />}
        action={
          blockedAction ? (
            <Button size="sm" onClick={blockedAction.onClick}>
              {blockedAction.label}
            </Button>
          ) : undefined
        }
      />
    )
  }

  return <>{children}</>
}
