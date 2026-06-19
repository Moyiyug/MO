import { cn } from '@/lib/utils'

interface BlueprintSkeletonProps {
  lines?: number
  className?: string
}

export function BlueprintSkeleton({ lines = 4, className }: BlueprintSkeletonProps) {
  return (
    <div
      className={cn(
        'mo-blueprint-panel space-y-3 p-5',
        className,
      )}
      role="status"
      aria-live="polite"
    >
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="h-3 rounded-sm border border-blue-200/60 bg-gradient-to-r from-blue-100/30 via-white/70 to-blue-100/30"
          style={{ width: `${92 - index * 9}%` }}
        />
      ))}
      <span className="sr-only">加载中</span>
    </div>
  )
}
