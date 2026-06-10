import type { ReactNode } from 'react'
import { AlertCircle, Inbox, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MOError } from '@/api/client'

interface QueryStateProps {
  isLoading?: boolean
  isError?: boolean
  error?: Error | null
  isEmpty?: boolean
  emptyTitle?: string
  emptyDescription?: string
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
      </div>
    )
  }

  return <>{children}</>
}
