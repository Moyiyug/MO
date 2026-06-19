import type { ReactNode } from 'react'
import { motion } from 'motion/react'

import { cn } from '@/lib/utils'
import { useMotionSafe } from './useMotionSafe'

interface BlueprintPanelProps {
  children: ReactNode
  label?: string
  index?: string | number
  accent?: 'blue' | 'amber' | 'green' | 'red' | 'slate'
  className?: string
  contentClassName?: string
  as?: 'section' | 'div' | 'article'
}

const ACCENT_CLASS: Record<NonNullable<BlueprintPanelProps['accent']>, string> = {
  blue: 'before:border-blue-500/70 after:border-blue-500/70',
  amber: 'before:border-amber-500/70 after:border-amber-500/70',
  green: 'before:border-emerald-500/70 after:border-emerald-500/70',
  red: 'before:border-red-500/70 after:border-red-500/70',
  slate: 'before:border-slate-400/70 after:border-slate-400/70',
}

export function BlueprintPanel({
  children,
  label,
  index,
  accent = 'blue',
  className,
  contentClassName,
  as = 'section',
}: BlueprintPanelProps) {
  const motionSafe = useMotionSafe()
  const MotionTag =
    as === 'article' ? motion.article : as === 'div' ? motion.div : motion.section

  return (
    <MotionTag
      initial={motionSafe.initial}
      animate={motionSafe.animate}
      transition={motionSafe.transition}
      className={cn('mo-blueprint-panel mo-card-hover', ACCENT_CLASS[accent], className)}
    >
      {(label || index !== undefined) && (
        <div className="pointer-events-none absolute right-3 top-2 z-10 flex items-center gap-2 text-[10px] uppercase tracking-[0.24em] text-muted-foreground/70">
          {label && <span>{label}</span>}
          {index !== undefined && (
            <span className="rounded-full border border-[var(--mo-line)] bg-background/70 px-1.5 py-0.5 font-mono">
              {String(index).padStart(2, '0')}
            </span>
          )}
        </div>
      )}
      <div className={cn('relative z-10', contentClassName)}>{children}</div>
    </MotionTag>
  )
}
